"""ROK Dijital: takvim/ klasorundeki gonderileri zamani gelince Instagram'a ve Facebook sayfasina paylasir.

Her gonderi bir klasordur, adi paylasim zamanini tasir (Turkiye saati):

    takvim/2026-11-05_1000_whatsapp-onizleme/
        01.jpg 02.jpg ...      carousel kareleri (tek kare varsa tek gorsel paylasilir)
        01.mp4                 istege bagli: 1. karenin hareketli hali (Instagram'da video kare olur,
                               Facebook'ta 01.jpg kullanilir)
        aciklama.txt           gonderi metni

    takvim/2026-11-07_1000_yegenim-hallediyor/
        video.mp4              Reels videosu
        kapak.jpg              Reels kapagi
        aciklama.txt

Zamani gelen gonderi paylasilir ve paylasildi/ klasorune tasinir.
Takvimli paylasim yalnizca depoda AKTIF dosyasi varsa calisir (guvenlik anahtari).
Erisim anahtari yalnizca IG_ACCESS_TOKEN ortam degiskeninden okunur ve asla yazdirilmaz.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

GRAPH_VERSION = os.environ.get("GRAPH_VERSION", "v24.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
GRAPH_VIDEO = f"https://graph-video.facebook.com/{GRAPH_VERSION}"
TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG_ID = os.environ["IG_USER_ID"]
REPO = os.environ.get("GITHUB_REPOSITORY", "")
MODE = os.environ.get("MOD", "takvim")  # takvim | kontrol | simdi
TARGET = os.environ.get("KLASOR", "").strip()
DRY = os.environ.get("DENEME", "false") == "true"
ONLY_IG = os.environ.get("SADECE_INSTAGRAM", "false") == "true"

TZ = ZoneInfo("Europe/Istanbul")
QUEUE = Path("takvim")
DONE = Path("paylasildi")
SWITCH = Path("AKTIF")
COVER_MS = "6500"  # hareketli karelerde kapak: animasyonun bittigi an (ilk kare bos)
LATE_LIMIT = timedelta(hours=20)  # GitHub zamanlayicisi saatlerce gecikebiliyor; bundan gec kalan paylasilmaz


def mask(value):
    print(f"::add-mask::{value}")


def api(method, path, base=GRAPH, files=None, **params):
    url = path if path.startswith("http") else f"{base}/{path}"
    if method == "POST":
        r = requests.post(url, data=params, files=files, timeout=300)
    else:
        r = requests.get(url, params=params, timeout=60)
    try:
        body = r.json()
    except ValueError:
        body = {"error": {"message": r.text[:300]}}
    if r.status_code != 200 or (isinstance(body, dict) and "error" in body):
        err = body.get("error", {}) if isinstance(body, dict) else {}
        raise RuntimeError(f"Graph API hatasi ({path.split('?')[0].split('/')[-1]}): "
                           f"{err.get('error_user_msg') or err.get('message', body)}")
    return body


def git(*args):
    subprocess.run(["git", *args], check=True)


def find_page():
    """Instagram hesabina bagli Facebook sayfasini ve sayfa anahtarini bulur."""
    data = api("GET", "me/accounts", fields="id,name,access_token,instagram_business_account",
               access_token=TOKEN)
    for page in data.get("data", []):
        if page.get("instagram_business_account", {}).get("id") == IG_ID:
            mask(page["access_token"])
            return page
    raise RuntimeError("Instagram hesabina bagli Facebook sayfasi bulunamadi.")


def check_permissions():
    """Anahtarda paylasim icin gereken izinler var mi?"""
    need = {"instagram_basic", "instagram_content_publish", "pages_show_list",
            "pages_read_engagement", "pages_manage_posts"}
    data = api("GET", "me/permissions", access_token=TOKEN).get("data", [])
    have = {p["permission"] for p in data if p.get("status") == "granted"}
    missing = sorted(need - have)
    if missing:
        print(f"UYARI: anahtarda eksik izin(ler): {', '.join(missing)}")
    else:
        print("Izinler tamam: " + ", ".join(sorted(need)))
    return not missing


# ---------------------------------------------------------------- gonderi okuma

def parse_when(folder):
    """'2026-11-05_1000_slug' -> Turkiye saatiyle datetime."""
    date, hhmm = folder.name.split("_")[:2]
    return datetime.strptime(f"{date} {hhmm}", "%Y-%m-%d %H%M").replace(tzinfo=TZ)


def load_post(folder):
    caption_file = folder / "aciklama.txt"
    caption = caption_file.read_text(encoding="utf-8").strip() if caption_file.exists() else ""
    if (folder / "video.mp4").exists():
        return {"kind": "reels", "video": folder / "video.mp4",
                "cover": folder / "kapak.jpg" if (folder / "kapak.jpg").exists() else None,
                "caption": caption}
    slides = sorted(folder.glob("[0-9][0-9].jpg"))
    if not slides:
        raise RuntimeError(f"{folder.name}: gorsel bulunamadi")
    items = []
    for jpg in slides:
        mp4 = jpg.with_suffix(".mp4")
        items.append({"jpg": jpg, "mp4": mp4 if mp4.exists() else None})
    return {"kind": "carousel" if len(items) > 1 else "single", "items": items, "caption": caption}


def raw_url(path, sha):
    return f"https://raw.githubusercontent.com/{REPO}/{sha}/{path.as_posix()}"


# ---------------------------------------------------------------- Instagram

def wait_ready(container, what):
    for _ in range(60):
        info = api("GET", container, fields="status_code,status", access_token=TOKEN)
        code = info.get("status_code")
        if code == "FINISHED":
            return
        if code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram {what} isleyemedi: {info.get('status', code)}")
        time.sleep(5)
    raise RuntimeError(f"Instagram {what} zamaninda hazir olmadi")


def upload_video(container_info, path):
    """Videoyu Instagram'a dogrudan yukler (herkese acik adrese gerek yok)."""
    data = path.read_bytes()
    r = requests.post(container_info["uri"], data=data, timeout=600, headers={
        "Authorization": f"OAuth {TOKEN}", "offset": "0", "file_size": str(len(data)),
        "Content-Type": "application/octet-stream"})
    if r.status_code != 200:
        raise RuntimeError(f"Instagram video yuklemesi basarisiz: {r.text[:300]}")


def ig_video_container(path, sha=None, **params):
    """Once dogrudan yuklemeyi dener; olmazsa videoyu GitHub adresinden cektirir."""
    try:
        info = api("POST", f"{IG_ID}/media", upload_type="resumable", access_token=TOKEN, **params)
        upload_video(info, path)
        return info["id"]
    except Exception as e:  # noqa: BLE001
        if not sha:
            raise
        print(f"Dogrudan yukleme olmadi ({e}); adresten cekme deneniyor.")
        return api("POST", f"{IG_ID}/media", video_url=raw_url(path, sha), access_token=TOKEN,
                   **params)["id"]


def publish_instagram(post, sha):
    caption = post["caption"]
    if post["kind"] == "reels":
        extra = {"cover_url": raw_url(post["cover"], sha)} if post["cover"] else {}
        cid = ig_video_container(post["video"], sha, media_type="REELS", caption=caption,
                                 share_to_feed="true", **extra)
        wait_ready(cid, "Reels videosunu")
    elif post["kind"] == "single":
        item = post["items"][0]
        if item["mp4"]:
            cid = ig_video_container(item["mp4"], sha, media_type="REELS", caption=caption,
                                     share_to_feed="true", cover_url=raw_url(item["jpg"], sha))
        else:
            cid = api("POST", f"{IG_ID}/media", image_url=raw_url(item["jpg"], sha),
                      caption=caption, access_token=TOKEN)["id"]
        wait_ready(cid, "gorseli")
    else:
        children = []
        for item in post["items"]:
            if item["mp4"]:
                child = ig_video_container(item["mp4"], sha, media_type="VIDEO",
                                           is_carousel_item="true", thumb_offset=COVER_MS)
            else:
                child = api("POST", f"{IG_ID}/media", image_url=raw_url(item["jpg"], sha),
                            is_carousel_item="true", access_token=TOKEN)["id"]
            children.append(child)
        for child in children:
            wait_ready(child, "carousel karesini")
        cid = api("POST", f"{IG_ID}/media", media_type="CAROUSEL", children=",".join(children),
                  caption=caption, access_token=TOKEN)["id"]
        wait_ready(cid, "carousel'i")
    return api("POST", f"{IG_ID}/media_publish", creation_id=cid, access_token=TOKEN)["id"]


# ---------------------------------------------------------------- Facebook

def publish_facebook(page, post, sha):
    token = page["access_token"]
    caption = post["caption"]
    if post["kind"] == "reels":
        with post["video"].open("rb") as fh:
            return api("POST", f"{page['id']}/videos", base=GRAPH_VIDEO,
                       files={"source": ("video.mp4", fh, "video/mp4")},
                       description=caption, access_token=token)["id"]
    jpgs = [item["jpg"] for item in post["items"]]
    if len(jpgs) == 1:
        return api("POST", f"{page['id']}/photos", url=raw_url(jpgs[0], sha), message=caption,
                   published="true", access_token=token)["post_id"]
    media = {}
    for i, jpg in enumerate(jpgs):
        fbid = api("POST", f"{page['id']}/photos", url=raw_url(jpg, sha), published="false",
                   access_token=token)["id"]
        media[f"attached_media[{i}]"] = json.dumps({"media_fbid": fbid})
    return api("POST", f"{page['id']}/feed", message=caption, access_token=token, **media)["id"]


# ---------------------------------------------------------------- akis

def due_posts(now):
    if MODE == "simdi":
        folder = Path(TARGET) if "/" in TARGET else QUEUE / TARGET
        if not TARGET or not folder.is_dir():
            raise RuntimeError(f"Klasor bulunamadi: {folder}")
        return [folder]
    due = []
    for folder in sorted(p for p in QUEUE.glob("*") if p.is_dir()):
        try:
            when = parse_when(folder)
        except ValueError:
            print(f"Atlandi (klasor adi tarih_saat_ad bicminde degil): {folder.name}")
            continue
        if when > now:
            continue
        if now - when > LATE_LIMIT:
            print(f"Atlandi (zamani {LATE_LIMIT} saatten fazla gecmis): {folder.name}")
            continue
        due.append(folder)
    return due


def main():
    page = find_page()
    print(f"Baglanti tamam: Facebook sayfasi '{page['name']}', Instagram id {IG_ID}")
    perms_ok = check_permissions()
    now = datetime.now(TZ)

    if MODE == "kontrol":
        upcoming = sorted(p.name for p in QUEUE.glob("*") if p.is_dir()) if QUEUE.exists() else []
        print(f"Takvimde {len(upcoming)} gonderi var. Siradaki: {upcoming[:3]}")
        print("Takvimli paylasim: " + ("ACIK" if SWITCH.exists() else "KAPALI (AKTIF dosyasi yok)"))
        for name in upcoming:
            load_post(QUEUE / name)  # bicim hatasi varsa simdiden gorunsun
        return
    if MODE == "takvim" and not SWITCH.exists():
        print("Takvimli paylasim kapali (AKTIF dosyasi yok). Cikiliyor.")
        return
    if not perms_ok:
        sys.exit("Eksik izin varken paylasim yapilmaz.")

    folders = due_posts(now)
    if not folders:
        print("Zamani gelen gonderi yok.")
        return

    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    DONE.mkdir(exist_ok=True)
    failed = 0
    for folder in folders:
        post = load_post(folder)
        print(f"\n== {folder.name} ({post['kind']}) ==")
        if DRY:
            print("DENEME: paylasim yapilmadi.")
            continue
        log = []
        try:
            ig = publish_instagram(post, sha)
            log.append(f"instagram {ig}")
            print(f"Instagram'da paylasildi (medya id {ig})")
        except Exception as e:  # noqa: BLE001
            print(f"HATA Instagram: {e}")
            failed += 1
            continue  # Instagram olmadan Facebook'a da gecme; klasor takvimde kalir
        try:
            if ONLY_IG:
                raise RuntimeError("atlandi (sadece Instagram istendi)")
            fb = publish_facebook(page, post, sha)
            log.append(f"facebook {fb}")
            print(f"Facebook'ta paylasildi (gonderi id {fb})")
        except Exception as e:  # noqa: BLE001
            log.append(f"facebook {e}" if ONLY_IG else f"facebook HATA {e}")
            print(f"Facebook: {e}" if ONLY_IG else f"HATA Facebook: {e}")
            failed += 0 if ONLY_IG else 1
        (folder / "sonuc.txt").write_text("\n".join(log) + f"\n{now.isoformat()}\n", encoding="utf-8")
        git("add", "-A", str(folder))
        git("mv", str(folder), str(DONE / folder.name))
        git("commit", "-m", f"Paylasildi: {folder.name}")
        git("push")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
