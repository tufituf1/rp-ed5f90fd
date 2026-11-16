# ROK Dijital otomatik paylaşım

`takvim/` klasöründeki her gönderi, zamanı gelince **Instagram** ve **ROK Dijital Facebook sayfasında** paylaşılır. Arka planda sürekli açık duran bir "bekçi" iş, gönderinin saatini bekleyip tam zamanında paylaşır.

## Takvim

Her gönderi bir klasördür. Klasör adı paylaşım zamanını taşır (Türkiye saati):

```
takvim/2026-11-05_1215_whatsapp-onizleme/
    01.jpg 02.jpg ...   carousel kareleri (tek kare varsa tek görsel)
    01.mp4              isteğe bağlı: 1. karenin hareketli hali (Facebook'ta 01.jpg kullanılır)
    aciklama.txt        gönderi metni

takvim/2026-11-07_1800_yegenim-hallediyor/
    video.mp4           Reels
    kapak.jpg           Reels kapağı
    aciklama.txt
```

- Görseller 12:15'te, Reels 18:00'de paylaşılır.
- Paylaşılan gönderi `paylasildi/` klasörüne taşınır, içine `sonuc.txt` yazılır.
- Zamanı 20 saatten fazla geçmiş gönderi otomatik paylaşılmaz (yanlışlıkla toplu paylaşımı önler).
- Bekçi iş yaklaşık 5,5 saatte bir kendini yeniden başlatır; zincir koparsa saatlik zamanlayıcı onu tekrar ayağa kaldırır.
- Bir gönderiyi iptal etmek için klasörünü silin; saatini değiştirmek için klasör adını değiştirin.

## Açma / kapatma

Takvimli paylaşım yalnızca depoda `AKTIF` adlı dosya varsa çalışır. Durdurmak için `AKTIF` dosyasını silin; bekçi de kendini kapatır.

## Elle çalıştırma

Actions › "Instagram ve Facebook paylasimi" › Run workflow:

- `kontrol`: bağlantıyı, izinleri ve takvimi kontrol eder, paylaşım yapmaz.
- `simdi`: `klasor` alanına yazılan gönderiyi hemen paylaşır.
- `takvim`: zamanı gelenleri bir kere paylaşır.
- `bekci`: bekçiyi elle başlatır (normalde kendiliğinden çalışır).

## Notlar

- Depo herkese açıktır: takvimdeki görseller ve metinler paylaşımdan önce de görülebilir.
- Erişim anahtarı yalnızca `IG_ACCESS_TOKEN` gizli değişkeninde durur, koda yazılmaz.
- Bir paylaşım hata verirse GitHub size e-posta gönderir; gönderi takvimde kalır.
