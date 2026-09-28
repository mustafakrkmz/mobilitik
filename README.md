# Mobilitik

Mobilya sektöründeki tüketici şikâyetlerini akademik araştırma amacıyla toplamak, yapılandırmak ve analiz etmek için geliştirilen açık kaynak masaüstü araç.

## İlk hedef

Şikayetvar üzerindeki herkese açık firma şikâyetlerini düşük hızda ve araştırma odaklı şekilde toplamak; kayıtları firma, tarih, başlık, tam metin, çözülme durumu ve firma yanıtı gibi alanlarla SQLite veritabanına kaydetmek.

## Kurulum

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium
```

## Masaüstü uygulamasını çalıştırma

```bash
python -m mobilitik.desktop
```

Arayüz üzerinden:

- firma seçilebilir veya Şikayetvar firma slug'ı elle yazılabilir,
- başlangıç ve bitiş tarihi seçilebilir,
- taranacak maksimum sayfa sayısı belirlenebilir,
- veri toplama başlatılıp durdurulabilir,
- toplanan kayıtlar yerel tabloda görüntülenebilir,
- toplam şikâyet, çözülme oranı ve firma yanıt oranı görülebilir,
- veriler CSV veya Excel olarak dışa aktarılabilir.

İlk test için `max_pages=3` gibi küçük bir değer kullanılması önerilir.

## Komut satırı kullanımı

Örnek olarak bir firma için ilk 3 sayfayı taramak:

```bash
scrapy crawl complaints -a company=istikbal -a max_pages=3
```

Belirli tarih aralığını hedeflemek:

```bash
scrapy crawl complaints \
  -a company=istikbal \
  -a start_date=2026-01-01 \
  -a end_date=2026-09-28
```

Başka bir firma için yalnızca `company` slug'ını değiştirin:

```bash
scrapy crawl complaints -a company=bellona -a max_pages=5
```

Veriler varsayılan olarak `mobilitik.db` dosyasındaki `complaints` tablosuna yazılır. Aynı şikâyet URL'si tekrar görülürse yeni satır oluşturmak yerine mevcut kayıt güncellenir.

## Veri alanları

- `company`
- `complaint_url`
- `complaint_date`
- `title`
- `complaint_text`
- `resolved`
- `company_responded`
- `company_response_text`
- `listing_page`
- `scraped_at`

## Notlar

- `ROBOTSTXT_OBEY = True` ve düşük istek eşzamanlılığı varsayılan olarak etkindir.
- Şikayetvar HTML yapısını değiştirdiğinde CSS seçicilerinin güncellenmesi gerekebilir.
- `Çözüldü` durumu ilk sürümde sayfa metninden muhafazakâr biçimde tespit edilmektedir. Çözüm tarihi ve gerçek çözüm süresi ayrı bir doğrulama aşamasında eklenecektir.
- Tarihte yıl görünmediğinde mevcut yıl körlemesine atanmaz; yıl geçişlerinde geçmiş tarih olasılığı dikkate alınır.
- Masaüstü arayüz şu aşamada geliştirme sürümüdür; ilk amaç veri toplama ve kayıt akışını doğrulamaktır.

## Yol haritası

1. Gerçek Şikayetvar sayfalarında seçicileri doğrulama
2. Firma yanıt tarihini çıkarma
3. Çözüm tarihini ve çözüm süresini çıkarma
4. Mobilya şikâyet kategorilerini tanımlama
5. Masaüstü analiz ekranını geliştirme
6. Firma karşılaştırmalı istatistik ve görselleştirme
7. Windows için tek dosyalı/kurulumlu dağıtım hazırlama
