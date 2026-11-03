# ROK Dijital otomatik paylaşım

`posts/` klasörüne yüklenen her gönderi otomatik olarak **Instagram (@rokdijital)** ve **ROK Dijital Facebook sayfasında** paylaşılır.

## Gönderi nasıl eklenir

1. Görseli `posts/` klasörüne koyun (jpg, png veya webp; Instagram için kare 1:1 veya dikey 4:5 önerilir).
2. Açıklamayı aynı adla `.txt` dosyasına yazın (isteğe bağlı).

```
posts/2026-11-05-kampanya.jpg
posts/2026-11-05-kampanya.txt
```

3. Gönderin (commit + push). Paylaşım birkaç dakika içinde yapılır, dosyalar `paylasildi/` klasörüne taşınır.

## Notlar

- Depo herkese açıktır: `posts/` içine konan görsel ve metinler paylaşımdan önce de görülebilir.
- Erişim anahtarı yalnızca `IG_ACCESS_TOKEN` gizli değişkeninde durur, koda yazılmaz.
- Bağlantı testi: Actions › "Instagram ve Facebook paylasimi" › Run workflow (varsayılan olarak sadece kontrol eder, paylaşım yapmaz).
