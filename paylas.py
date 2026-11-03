"""ROK Dijital: posts/ klasorundeki gonderileri Instagram'a ve Facebook sayfasina paylasir.

Gonderi = bir gorsel (jpg/jpeg/png/webp) + ayni adli .txt aciklama dosyasi (istege bagli).
Ornek: posts/2026-11-05-kampanya.jpg  +  posts/2026-11-05-kampanya.txt

Paylasilan gonderiler paylasildi/ klasorune tasinir.
Erisim anahtari yalnizca IG_ACCESS_TOKEN ortam degiskeninden okunur ve asla yazdirilmaz.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from PIL import Image

GRAPH = f"https://graph.facebook.com/{os.environ.get('GRAPH_VERSION', 'v24.0')}"
TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG_ID = os.environ["IG_USER_ID"]
REPO = os.environ["GITHUB_REPOSITORY"]
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
ONLY_CHECK = os.environ.get("SADECE_KONTROL", "false") == "true"

POSTS = Path("posts")
DONE = Path("paylasildi")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def mask(value):
    print(f"::add-mask::{value}")


def api(method, path, **params):
    r = requests.request(method, f"{GRAPH}/{path}", data=params if method == "POST" else None,
                         params=None if method == "POST" else params, timeout=60)
    body = r.json()
    if r.status_code != 200 or "error" in body:
        err = body.get("error", {})
        raise RuntimeError(f"Graph API hatasi ({path.split('?')[0]}): {err.get('message', body)}")
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


def to_jpeg(path):
    """Instagram yalnizca JPEG kabul eder; gerekirse donusturur."""
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return path
    new = path.with_suffix(".jpg")
    Image.open(path).convert("RGB").save(new, "JPEG", quality=92)
    path.unlink()
    return new


def publish_instagram(image_url, caption):
    container = api("POST", f"{IG_ID}/media", image_url=image_url, caption=caption,
                    access_token=TOKEN)["id"]
    for _ in range(30):
        status = api("GET", container, fields="status_code", access_token=TOKEN)["status_code"]
        if status == "FINISHED":
            break
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram gorseli isleyemedi (durum: {status}).")
        time.sleep(5)
    return api("POST", f"{IG_ID}/media_publish", creation_id=container, access_token=TOKEN)["id"]


def publish_facebook(page, image_url, caption):
    return api("POST", f"{page['id']}/photos", url=image_url, message=caption,
               published="true", access_token=page["access_token"])["post_id"]


def main():
    page = find_page()
    print(f"Baglanti tamam: Facebook sayfasi '{page['name']}', Instagram id {IG_ID}")
    if ONLY_CHECK:
        return

    images = sorted(p for p in POSTS.glob("*") if p.suffix.lower() in IMAGE_EXT)
    if not images:
        print("posts/ klasorunde paylasilacak gonderi yok.")
        return

    # 1) Gorselleri JPEG'e cevir ve gonder ki herkese acik adresleri olsun.
    images = [to_jpeg(p) for p in images]
    git("add", "-A", str(POSTS))
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        git("commit", "-m", "Gorseller JPEG'e cevrildi")
        git("push")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()

    DONE.mkdir(exist_ok=True)
    failed = 0
    for img in images:
        txt = img.with_suffix(".txt")
        caption = txt.read_text(encoding="utf-8").strip() if txt.exists() else ""
        url = f"https://raw.githubusercontent.com/{REPO}/{sha}/{img.as_posix()}"
        print(f"\n== {img.name} ==")
        try:
            ig = publish_instagram(url, caption)
            print(f"Instagram'da paylasildi (medya id {ig})")
        except Exception as e:  # noqa: BLE001
            print(f"HATA Instagram: {e}")
            failed += 1
            continue
        try:
            fb = publish_facebook(page, url, caption)
            print(f"Facebook'ta paylasildi (gonderi id {fb})")
        except Exception as e:  # noqa: BLE001
            print(f"HATA Facebook: {e}")
            failed += 1
        git("mv", str(img), str(DONE / img.name))
        if txt.exists():
            git("mv", str(txt), str(DONE / txt.name))

    git("add", "-A")
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        git("commit", "-m", "Paylasilan gonderiler paylasildi/ klasorune tasindi")
        git("push")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
