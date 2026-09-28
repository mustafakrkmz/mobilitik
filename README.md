# Mobilitik

Mobilya sektöründeki tüketici şikâyetlerini akademik araştırma amacıyla toplamak, yapılandırmak ve analiz etmek için geliştirilen açık kaynak masaüstü araç.

## Amaç

Şikayetvar üzerindeki herkese açık firma şikâyetlerini düşük hızda ve araştırma odaklı şekilde toplamak; kayıtları firma, tarih, başlık, tam metin, çözülme durumu, firma yanıtı ve mümkün olduğunda yanıt/çözüm süreleriyle SQLite veritabanına kaydetmek ve seçilen firma/tarih aralığı için tekrarlanabilir analiz üretmek.

## Windows — en kolay kurulum

1. GitHub'da yeşil **Code** düğmesine basın.
2. **Download ZIP** ile projeyi indirin.
3. ZIP dosyasını normal bir klasöre çıkarın.
4. **`install_windows.bat`** dosyasına çift tıklayın.
5. Kurulum bittiğinde masaüstündeki **Mobilitik** kısayolunu açın.

Kurucu sanal Python ortamını, gerekli paketleri ve Playwright Chromium'u otomatik hazırlar. Python bulunamazsa ve Windows Package Manager (`winget`) varsa Python 3.12 kurulumunu da başlatabilir.

Ayrıntılı Türkçe yönerge: **[WINDOWS_KURULUM.md](WINDOWS_KURULUM.md)**

## Elle kurulum

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
- seçili firma ve dönem için toplam şikâyet, çözülme oranı ve firma yanıt oranı görülebilir,
- açık tarih verisi varsa medyan firma yanıt süresi ve medyan çözüm süresi hesaplanabilir,
- kategori bazında yanıt ve çözüm süreleri karşılaştırılabilir,
- kategori analizi yapılabilir,
- tek kelime, bigram ve trigram sıklıkları incelenebilir,
- TF-IDF ağırlıkları ve belge sıklıkları görüntülenebilir,
- her şikâyet kategorisini diğerlerinden ayıran kelime/n-gram ifadeleri incelenebilir,
- veriler CSV veya Excel olarak dışa aktarılabilir.

## Yanıt ve çözüm süreleri

Mobilitik süre üretirken muhafazakâr davranır:

- Şikâyetin yayın tarihi ile firma yanıtının açık tarihi bulunuyorsa `response_hours` hesaplanır.
- Şikâyet çözülmüşse ve çözüm/sonuç bölümünde açık tarih bulunuyorsa `resolution_hours` hesaplanır.
- Sayfada yalnızca `Çözüldü` etiketi bulunuyor fakat çözüm tarihi görünmüyorsa çözülme durumu kaydedilir, **çözüm süresi tahmin edilmez**.
- İmkânsız kronoloji (ör. yanıt tarihi şikâyetten önce) görülürse süre boş bırakılır.

Bu yaklaşım, eksik platform verisini araştırma verisi gibi göstermemek için bilinçli olarak seçilmiştir.

## Kategori analizi

İlk sınıflandırma motoru ağırlıklı anahtar kelime/ifade eşleşmesine dayanır. Eşleşmeler kelime/ifade sınırlarıyla yapılır; kısa anahtar kelimelerin başka kelimelerin içinde yanlış pozitif üretmesi engellenir. Bir şikâyet birden fazla kategoriye atanabilir.

Başlangıç kategorileri:

- Teslimat / Lojistik
- Üretim / Kalite
- Aksesuar / Donanım
- Montaj / Servis
- İade / Ücret
- Satış / İletişim
- Diğer

Her kategori için şikâyet sayısı, çözülen şikâyet sayısı, çözülme oranı, firma yanıt oranı ve veri mevcutsa medyan yanıt/çözüm süresi hesaplanır. Kategori sözlüğü gerçek verilerden elde edilen kelime ve n-gram bulgularına göre kalibre edilecektir.

## Kelime analizi

Seçili firma ve tarih aralığı için şikâyet başlığı ile tam metin birlikte analiz edilir.

- Türkçe karakterler analiz amacıyla normalize edilir.
- Sık işlev sözcükleri stop-word filtresinden geçirilir.
- Unigram, bigram ve trigram frekansları hesaplanır.
- Her ifade için kaç farklı şikâyette görüldüğü hesaplanır.
- TF-IDF ağırlığı ile yalnızca sık değil, daha ayırt edici ifadeler de öne çıkarılır.

Bu katman özellikle `teslimat tarihi`, `servis kaydı`, `koltuk kumaşı`, `mekanizma arızası` gibi tekrarlayan sorun kalıplarını keşfetmek ve kategori sözlüğünü veriyle geliştirmek için kullanılacaktır.

## Kategoriye özgü ifadeler

`Kategori İfadeleri` sekmesi, her kategorideki şikâyetleri diğer kategorilerle karşılaştırır ve o kategori için görece daha ayırt edici olan unigram, bigram veya trigramları sıralar. Böylece önceden tanımlanmamış fakat gerçek veride sık tekrar eden sorun kalıpları kategori sözlüğüne kontrollü biçimde eklenebilir.

## Otomatik testler

GitHub Actions üzerinde otomatik test paketi çalışır. Test kapsamı şunları içerir:

- Türkçe ve ISO tarih ayrıştırma,
- yanıt/çözüm sürelerinin hesaplanması ve negatif sürelerin reddedilmesi,
- kategori sınıflandırma ve çoklu kategori davranışı,
- yanlış alt-kelime eşleşmelerinin engellenmesi,
- kategori özetleri, çözülme/yanıt oranları ve medyan süreler,
- unigram/bigram/trigram, belge sıklığı ve TF-IDF,
- kategoriye özgü ayırt edici ifade analizi,
- SQLite pipeline insert/update ve eski veritabanı şema migrasyonu,
- veritabanı firma/tarih filtreleri,
- CSV ve Excel dışa aktarma,
- örnek Şikayetvar HTML'i üzerinden liste/detay parser davranışı,
- masaüstü arayüzünün headless ortamda açılması ve analiz tablolarını doldurması,
- masaüstü arayüzünün scraper komutunu doğru kurması ve Başlat/Durdur akışı.

CI, toplam test kapsamı %85'in altına düştüğünde başarısız olur.

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
- `company_response_date`
- `response_hours`
- `resolution_text`
- `resolution_date`
- `resolution_hours`
- `listing_page`
- `scraped_at`

## Notlar

- `ROBOTSTXT_OBEY = True` ve düşük istek eşzamanlılığı varsayılan olarak etkindir.
- Şikayetvar HTML yapısını değiştirdiğinde CSS seçicilerinin güncellenmesi gerekebilir.
- Çözülme durumu liste kartındaki işaretten alınmaktadır.
- Yanıt/çözüm tarihleri yalnızca açıkça yayınlandığında kullanılır.
- Tarihte yıl görünmediğinde mevcut yıl körlemesine atanmaz; yıl geçişlerinde geçmiş tarih olasılığı dikkate alınır.
- Otomatik testler uygulama mantığını ve örnek HTML parser davranışını doğrular; harici sitenin gelecekteki DOM değişikliklerini garanti edemez.

## Yol haritası

1. Kategori sözlüğünü gerçek mobilya şikâyetleriyle kalibre etme
2. Firma karşılaştırmalı grafikler ve zaman serileri
3. Analiz sonuçlarını filtreli Excel/rapor olarak dışa aktarma
4. Python gerektirmeyen bağımsız Windows paketleme seçeneğini geliştirme
