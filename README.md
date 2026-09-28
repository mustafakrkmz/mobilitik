# Mobilitik

Mobilya sektöründeki tüketici şikâyetlerini akademik araştırma amacıyla toplamak, yapılandırmak ve analiz etmek için geliştirilen açık kaynak masaüstü araç.

## Amaç

Şikayetvar üzerindeki herkese açık firma şikâyetlerini düşük hızda ve araştırma odaklı şekilde toplamak; kayıtları firma, tarih, başlık, tam metin, çözülme durumu ve firma yanıtı gibi alanlarla SQLite veritabanına kaydetmek ve seçilen firma/tarih aralığı için tekrarlanabilir analiz üretmek.

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
- kategori analizi yapılabilir,
- tek kelime, bigram ve trigram sıklıkları incelenebilir,
- TF-IDF ağırlıkları ve belge sıklıkları görüntülenebilir,
- veriler CSV veya Excel olarak dışa aktarılabilir.

## Kategori analizi

İlk sınıflandırma motoru ağırlıklı anahtar kelime/ifade eşleşmesine dayanır. Bir şikâyet birden fazla kategoriye atanabilir.

Başlangıç kategorileri:

- Teslimat / Lojistik
- Üretim / Kalite
- Aksesuar / Donanım
- Montaj / Servis
- İade / Ücret
- Satış / İletişim
- Diğer

Her kategori için şikâyet sayısı, çözülen şikâyet sayısı, çözülme oranı ve firma yanıt oranı hesaplanır. Kategori sözlüğü gerçek verilerden elde edilen kelime ve n-gram bulgularına göre kalibre edilecektir.

## Kelime analizi

Seçili firma ve tarih aralığı için şikâyet başlığı ile tam metin birlikte analiz edilir.

- Türkçe karakterler analiz amacıyla normalize edilir.
- Sık işlev sözcükleri stop-word filtresinden geçirilir.
- Unigram, bigram ve trigram frekansları hesaplanır.
- Her ifade için kaç farklı şikâyette görüldüğü hesaplanır.
- TF-IDF ağırlığı ile yalnızca sık değil, daha ayırt edici ifadeler de öne çıkarılır.

Bu katman özellikle `teslimat tarihi`, `servis kaydı`, `koltuk kumaşı`, `mekanizma arızası` gibi tekrarlayan sorun kalıplarını keşfetmek ve kategori sözlüğünü veriyle geliştirmek için kullanılacaktır.

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
- Çözülme durumu liste kartındaki işaretten alınmaktadır.
- Firma yanıtının ve özellikle yanıt/çözüm tarihinin seçicileri ayrıca doğrulanmaya devam etmektedir.
- Tarihte yıl görünmediğinde mevcut yıl körlemesine atanmaz; yıl geçişlerinde geçmiş tarih olasılığı dikkate alınır.
- Masaüstü arayüz geliştirme sürümüdür; Windows paketleme aşamasından önce gerçek makinede uçtan uca test yapılacaktır.

## Yol haritası

1. Firma yanıt tarihi ve çözüm tarihini güvenilir biçimde çıkarma
2. Yanıt ve çözüm süresi metrikleri
3. Kategori sözlüğünü gerçek mobilya şikâyetleriyle kalibre etme
4. Kategoriye özgü ayırt edici kelime/n-gram analizi
5. Firma karşılaştırmalı grafikler ve zaman serileri
6. Analiz sonuçlarını Excel/rapor olarak dışa aktarma
7. Windows için tek dosyalı/kurulumlu dağıtım hazırlama
