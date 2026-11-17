#!/usr/bin/env bash
# Bekci: GitHub'in kendi zamanlayicisi saatlerce gecikebildigi icin bu is ~5,5 saat acik kalir,
# takvimdeki gonderinin saatini bekleyip tam zamaninda paylasir, sonra kendini yeniden baslatir.
# Durdurmak icin AKTIF dosyasini silin.
set -u
BITIS=$((SECONDS + 5*3600 + 20*60))
HATA=0

kalan_saniye() {
  python3 - <<'EOF'
import re, datetime, zoneinfo, pathlib
tz = zoneinfo.ZoneInfo("Europe/Istanbul")
now = datetime.datetime.now(tz)
best = None
for p in pathlib.Path("takvim").glob("*"):
    m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{4})_", p.name)
    if not m or not p.is_dir():
        continue
    t = datetime.datetime.strptime(m[1] + m[2], "%Y-%m-%d%H%M").replace(tzinfo=tz)
    s = (t - now).total_seconds()
    if -20 * 3600 < s <= 0:
        best = 0
        break
    if s > 0 and (best is None or s < best):
        best = s
print(int(best) if best is not None else 999999)
EOF
}

while [ "$SECONDS" -lt "$BITIS" ]; do
  git pull -q --rebase origin "${GITHUB_REF_NAME:-main}" || true
  if [ ! -f AKTIF ]; then
    echo "AKTIF dosyasi yok, bekci duruyor."
    exit 0
  fi
  KALAN=$(kalan_saniye)
  if [ "$KALAN" -eq 0 ]; then
    echo "== $(TZ=Europe/Istanbul date '+%d.%m %H:%M') paylasim zamani =="
    MOD=takvim python paylas.py || HATA=1
    sleep 300   # hata olursa ayni gonderiyi hemen tekrar denememek icin
    continue
  fi
  UYKU=$(( KALAN < 600 ? KALAN + 20 : 600 ))
  [ $((SECONDS + UYKU)) -gt "$BITIS" ] && UYKU=$((BITIS - SECONDS))
  [ "$UYKU" -gt 0 ] && sleep "$UYKU"
done

echo "Sure doldu, bekci yeniden baslatiliyor."
gh workflow run paylas.yml --ref main -f mod=bekci
exit $HATA
