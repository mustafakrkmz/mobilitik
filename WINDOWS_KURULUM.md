# Mobilitik — Windows Kurulumu

Mobilitik şu aşamada Windows üzerinde yerel Python ortamı ile çalışır. Kurulum betiği gerekli sanal ortamı ve Chromium tarayıcısını otomatik hazırlar.

## En kolay yöntem

1. GitHub'da Mobilitik reposunu açın.
2. Yeşil **Code** düğmesine basın.
3. **Download ZIP** seçeneğiyle projeyi indirin.
4. ZIP dosyasını bir klasöre çıkarın. Örneğin `Belgeler\Mobilitik`.
5. Klasör içindeki **`install_windows.bat`** dosyasına çift tıklayın.
6. Kurulum tamamlanınca masaüstünde **Mobilitik** kısayolu oluşur.
7. Bundan sonra uygulamayı bu kısayoldan açabilirsiniz.

Kurucu şunları otomatik yapar:

- Bilgisayarda uygun Python sürümünü kontrol eder.
- Python yoksa ve `winget` kullanılabiliyorsa Python 3.12 kurmayı dener.
- `.venv` isimli izole Python ortamı oluşturur.
- Scrapy, Playwright, PySide6 ve diğer bağımlılıkları kurar.
- Playwright için Chromium'u indirir.
- Masaüstüne Mobilitik kısayolu ekler.

## Elle çalıştırmak isterseniz

PowerShell veya Komut İstemi'ni proje klasöründe açıp:

```bat
.venv\Scripts\python.exe -m mobilitik.desktop
```

komutunu kullanabilirsiniz.

## Güncelleme

GitHub'dan yeni ZIP indirip mevcut proje klasörünün yerine yeni sürümü koyduktan sonra `install_windows.bat` dosyasını tekrar çalıştırabilirsiniz. Var olan `mobilitik.db` dosyanız araştırma verilerini içerir; güncelleme yaparken bu dosyayı ayrıca yedeklemeniz önerilir.

## Veriler nerede tutuluyor?

Uygulama verileri proje klasöründeki:

```text
mobilitik.db
```

dosyasında tutulur. Bu SQLite veritabanı başka bir bilgisayara taşınabilir ve yedeklenebilir.

## İlk kullanım önerisi

İlk denemede:

- Firma: `istikbal`
- Maksimum sayfa: `1` veya `2`
- Kısa bir tarih aralığı

seçerek küçük bir pilot tarama yapın. Sonuçlar doğru görünüyorsa sayfa sayısını ve tarih aralığını genişletin.

## Önemli not

Yanıt veya çözüm süresi yalnızca Şikayetvar sayfasında ilgili olayın tarihi açıkça bulunabiliyorsa hesaplanır. Tarih yayınlanmıyorsa Mobilitik süre tahmini yapmaz ve ilgili alanı boş bırakır.
