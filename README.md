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

Kurucu sanal Python ortamını, gerekli temel paketleri ve Playwright Chromium'u otomatik hazırlar. Python bulunamazsa ve Windows Package Manager (`winget`) varsa Python 3.12 kurulumunu da başlatabilir.

**BERTurk/PyTorch bileşenleri temel kurulumun parçası değildir.** Bunlar yalnızca `NLP / Duygu Analizi` sekmesindeki **NLP Bileşenlerini Kur / Güncelle** düğmesi kullanılırsa kurulur. Böylece NLP'yi hiç kullanmayan bir Mobilitik kurulumu gereksiz yere ağırlaşmaz.

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

- firma slug'ı veya doğrudan Şikayetvar firma **kök URL'si** girilebilir,
- örneğin `cilek-mobilya` ile `https://www.sikayetvar.com/cilek-mobilya` aynı firma olarak kabul edilir,
- kategori veya tekil şikâyet gibi kökten daha derin URL'ler bilinçli olarak reddedilir,
- başlangıç ve bitiş tarihi seçilebilir,
- **Filtreyi Uygula ve Analiz Et** ile şikâyet listesi ve temel analiz sekmeleri aynı firma/tarih filtresine göre yenilenir,
- taranacak maksimum sayfa sayısı belirlenebilir,
- veri toplama başlatılıp durdurulabilir,
- şikâyet başlığı veya URL bağlantısı üzerine gelindiğinde tam şikâyet metni araç ipucu olarak görülebilir,
- URL sütunundan kaynak şikâyet sayfası doğrudan açılabilir,
- seçili firma ve dönem için toplam şikâyet, çözülme oranı ve firma yanıt oranı görülebilir,
- açık tarih verisi varsa medyan firma yanıt süresi ve medyan çözüm süresi hesaplanabilir,
- kategori bazında yanıt ve çözüm süreleri karşılaştırılabilir,
- kategori analizi yapılabilir,
- şikâyetler kategoriye göre filtrelenebilir; **Tümü** seçeneği bütün kategorileri birlikte gösterir,
- tek kelime, bigram ve trigram sıklıkları Türkçe karakterler korunarak incelenebilir,
- TF-IDF ağırlıkları ve belge sıklıkları görüntülenebilir,
- `-ıyor/-iyor/-uyor/-üyor` biçimindeki fiiller yaklaşık gövde bazında analiz edilebilir ve aranabilir,
- her şikâyet kategorisini diğerlerinden ayıran kelime/n-gram ifadeleri incelenebilir,
- kategori adları ve kategoriye ait anahtar kelime/ifadeler kullanıcı tarafından elle düzenlenebilir,
- isteğe bağlı BERTurk duygu analizi ve aspect sentiment çalıştırılabilir,
- kümülatif kategori negatifliği ile gelişim öncelikleri kullanıcı ağırlıklarıyla hesaplanabilir,
- veriler CSV veya Excel olarak dışa aktarılabilir.

## İsteğe bağlı NLP / Duygu Analizi

`NLP / Duygu Analizi` sekmesi **otomatik çalışmaz**. Normal veri toplama veya temel analiz sırasında model yüklenmez. NLP yalnızca kullanıcı **Duygu Analizini Başlat** düğmesine bastığında çalışır.

Varsayılan model:

```text
incidelen/bert-base-turkish-sentiment-analysis-cased
```

Bu model BERTurk tabanlı, Türkçe e-ticaret yorumlarında `Negative / Neutral / Positive` sınıfları için fine-tune edilmiş hazır bir başlangıç modelidir. Mobilitik sonuçları Türkçe olarak `Negatif / Nötr / Pozitif` gösterir.

İlk kullanım akışı:

1. `NLP Bileşenlerini Kur / Güncelle` düğmesine basılır.
2. CPU-only PyTorch resmi CPU wheel kaynağından, ardından Transformers kurulur.
3. `Duygu Analizini Başlat` düğmesine basılır.
4. Model ilk analizde Hugging Face önbelleğine indirilir.
5. Sonraki çalışmalarda aynı model yeniden indirilmez.

### Önbellek ve tekrarlanabilirlik

Duygu sonuçları ana `complaints` tablosuna gömülmez. Ayrı ve sürümlenmiş tablolarda saklanır:

- `sentiment_results`
- `aspect_sentiment`

Önbellek anahtarı şu mantığa dayanır:

- şikâyet kimliği,
- model kimliği,
- Mobilitik analiz sürümü,
- başlık + metin SHA-256 özeti.

Metin ve model değişmediyse aynı şikâyet ikinci kez BERT'ten geçirilmez. Model veya analiz mantığı değiştirilirse eski sonuçlar silinmeden yeni sürüm ayrıca üretilebilir.

### Tekil duygu analizi

Her şikâyet için:

- baskın duygu sınıfı,
- sınıf güveni,
- negatif olasılığı,
- nötr olasılığı,
- pozitif olasılığı

saklanır ve tabloda gösterilir.

### Aspect sentiment

Şikâyet metni cümlelere ayrılır. Her cümle Mobilitik'in **manuel kategori kuralları** ile eşleştirilir; ardından cümle duygu skoru ilgili kategoriye yazılır. Böylece aynı şikâyette örneğin `Ürün/Kalite` olumlu, `Teslimat` çok negatif olabilir.

Bu yöntem tam denetimli bir Türkçe ABSA modeli değildir; mevcut manuel kategori kod kitabını BERT duygu skorlarıyla birleştiren, açıklanabilir bir ilk aspect-sentiment katmanıdır.

### Kümülatif gelişim öncelikleri

Kategori tablosunda şu metrikler birlikte gösterilir:

- kategori şikâyet sayısı ve toplam içindeki payı,
- ortalama negatiflik,
- `%70+` negatiflik taşıyan yüksek-negatif şikâyet oranı,
- çözülmeme oranı,
- mevcutsa ortalama firma yanıt süresi.

Mobilitik ayrıca karar desteği için `0–100` arası **Öncelik** göstergesi hesaplar. Varsayılan ağırlıklar:

```text
Sıklık      %40
Negatiflik  %35
Çözülmeme   %25
```

Bu ağırlıklar arayüzden değiştirilebilir. Öncelik puanı akademik bir kalite puanı olarak değil, hangi problem alanlarının birlikte sık + negatif + çözümsüz olduğunu görünür kılan şeffaf bir karar-destek göstergesi olarak kullanılmalıdır.

### Akademik kullanım uyarısı

Hazır BERTurk sentiment modeli e-ticaret yorumlarında eğitilmiştir; Şikayetvar mobilya şikâyetleri farklı bir domain'dir. Bu nedenle makalede modelin kaynak veri setindeki başarısı Mobilitik verisine doğrudan mal edilmemelidir. Araştırma kullanımında ayrı bir manuel doğrulama örneklemi üzerinde confusion matrix, accuracy, precision, recall ve macro-F1 raporlanması planlanmaktadır.

## Yanıt ve çözüm süreleri

Mobilitik süre üretirken muhafazakâr davranır:

- Şikâyetin yayın tarihi ile firma yanıtının açık tarihi bulunuyorsa `response_hours` hesaplanır.
- Şikâyet çözülmüşse ve çözüm/sonuç bölümünde açık tarih bulunuyorsa `resolution_hours` hesaplanır.
- Sayfada yalnızca `Çözüldü` etiketi bulunuyor fakat çözüm tarihi görünmüyorsa çözülme durumu kaydedilir, **çözüm süresi tahmin edilmez**.
- İmkânsız kronoloji (ör. yanıt tarihi şikâyetten önce) görülürse süre boş bırakılır.

Bu yaklaşım, eksik platform verisini araştırma verisi gibi göstermemek için bilinçli olarak seçilmiştir.

## Kategori analizi ve manuel kategori yönetimi

Kategoriler **Şikayetvar'dan alınmaz**. Mobilitik, kullanıcı tarafından düzenlenebilen ağırlıklı anahtar kelime/ifade eşleşmesi kullanır. Bir şikâyet birden fazla kategoriye atanabilir.

Başlangıç kategorileri yalnızca bir şablondur:

- Teslimat / Lojistik
- Üretim / Kalite
- Aksesuar / Donanım
- Montaj / Servis
- İade / Ücret
- Satış / İletişim
- Diğer

`Kategori Yönetimi` sekmesinde kategori adı ve ifadeler elle değiştirilebilir. İfade biçimi örneği:

```text
teslimat=3; teslim edilmedi=4; gecikme=3
```

Ağırlık yazılmazsa varsayılan değer `2` kullanılır. Kaydedilen kişisel kategori kuralları yerel `mobilitik_categories.json` dosyasında tutulur ve Git tarafından izlenmez.

`Kategori Analizi` tablosundaki **Tümü** satırı seçili dönem içindeki tüm kayıtları tek kez sayar. Kategori satırlarının toplamı daha yüksek olabilir; çünkü bir şikâyet birden fazla kategoriye girebilir.

## Kelime analizi

Seçili firma ve tarih aralığı için şikâyet başlığı ile tam metin birlikte analiz edilir.

- Türkçe `İ/ı/ş/ğ/ü/ö/ç` karakterleri korunur.
- Python'un `İ` harfinde oluşturabildiği birleşik Unicode problemi özel olarak ele alınır; örneğin `İstikbal` tek kelime olarak `istikbal` biçiminde kalır.
- Sık işlev sözcükleri stop-word filtresinden geçirilir.
- Unigram, bigram ve trigram frekansları hesaplanır.
- Her ifade için kaç farklı şikâyette görüldüğü hesaplanır.
- TF-IDF ağırlığı ile yalnızca sık değil, daha ayırt edici ifadeler de öne çıkarılır.

Bu katman özellikle `teslimat tarihi`, `servis kaydı`, `koltuk kumaşı`, `mekanizma arızası` gibi tekrarlayan sorun kalıplarını keşfetmek ve kategori sözlüğünü veriyle geliştirmek için kullanılır.

## Fiil analizi

`Fiil Analizi` sekmesi özellikle kullanıcının talep ettiği şimdiki zaman biçimlerine odaklanır:

- `-ıyor`
- `-iyor`
- `-uyor`
- `-üyor`

Örneğin `geliyor`, `bozuluyor`, `çalışıyor` gibi biçimler yakalanır; sıklık, farklı belge sayısı ve görülen çekimli örnekler listelenir. Bu modül tam bir Türkçe biçimbilim çözümleyicisi değildir. Sonuç bu nedenle arayüzde **yaklaşık gövde** olarak adlandırılır; özellikle `bekliyor` gibi ses değişimi içeren biçimlerde kök rekonstrüksiyonu yapılmaz.

## Kategoriye özgü ifadeler

`Kategori İfadeleri` sekmesi, her kategorideki şikâyetleri diğer kategorilerle karşılaştırır ve o kategori için görece daha ayırt edici olan unigram, bigram veya trigramları sıralar. **Tümü** seçeneği seçilen firma ve dönemdeki bütün şikâyetler için genel TF-IDF görünümünü verir.

## Otomatik testler

GitHub Actions üzerinde Linux ve Windows testleri çalışır. CI minimum coverage eşiği **%85**'tir. Gerçek `install_windows.bat` dosyası GitHub'ın Windows runner'ında çalıştırılır ve masaüstü smoke testleri aynı Windows ortamında yürütülür.

NLP testleri CI'da gerçek model ağırlığını indirmez. Bunun yerine kontrollü sahte model çıktısı kullanılarak şu zincir doğrulanır:

`şikâyet → duygu skorları → sürümlü cache → cümle/kategori aspect sentiment → kümülatif öncelik tablosu → PySide6 NLP sekmesi`.

Bu yaklaşım uygulama mantığını hızlı ve tekrarlanabilir biçimde test eder; gerçek modelin domain doğruluğu için ayrıca manuel doğrulama çalışması gerekir.

Test kapsamı ayrıca şunları içerir:

- Türkçe ve ISO tarih ayrıştırma,
- yanıt/çözüm sürelerinin hesaplanması ve negatif sürelerin reddedilmesi,
- kategori sınıflandırma ve çoklu kategori davranışı,
- kullanıcı tanımlı kategori kuralı kaydetme/okuma,
- yanlış alt-kelime eşleşmelerinin engellenmesi,
- `Tümü` dahil kategori özetleri, çözülme/yanıt oranları ve medyan süreler,
- Türkçe karakter korumalı unigram/bigram/trigram, belge sıklığı ve TF-IDF,
- kategoriye özgü ayırt edici ifade analizi,
- yaklaşık şimdiki-zaman fiil gövdesi analizi,
- SQLite pipeline insert/update ve eski veritabanı şema migrasyonu,
- veritabanı firma/tarih filtreleri,
- firma slug'ı ve Şikayetvar kök URL'si normalizasyonu,
- CSV ve Excel dışa aktarma,
- örnek Şikayetvar HTML'i üzerinden liste/detay parser davranışı,
- masaüstü arayüzünün headless ortamda açılması,
- firma/tarih filtresinin şikâyet satırlarını gerçekten değiştirmesi,
- kategori filtresi, tıklanabilir URL, hover şikâyet metni ve fiil filtresi,
- masaüstü arayüzünün scraper komutunu doğru kurması ve Başlat/Durdur akışı,
- NLP skor normalizasyonu, cache, aspect sentiment, kullanıcı ağırlıklı öncelik ve opt-in GUI akışı.

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

Ana şikâyet tablosu:

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

NLP sonuçları ayrı `sentiment_results` ve `aspect_sentiment` tablolarında sürümlü olarak tutulur.

## Notlar

- `ROBOTSTXT_OBEY = True` ve düşük istek eşzamanlılığı varsayılan olarak etkindir.
- Şikayetvar HTML yapısını değiştirdiğinde CSS seçicilerinin güncellenmesi gerekebilir.
- Çözülme durumu liste kartındaki işaretten alınmaktadır.
- Yanıt/çözüm tarihleri yalnızca açıkça yayınlandığında kullanılır.
- Tarihte yıl görünmediğinde mevcut yıl körlemesine atanmaz; yıl geçişlerinde geçmiş tarih olasılığı dikkate alınır.
- Otomatik testler uygulama mantığını ve örnek HTML parser davranışını doğrular; harici sitenin gelecekteki DOM değişikliklerini garanti edemez.
- BERTurk sonuçları hazır model çıktısıdır; mobilya şikâyeti domain'inde manuel doğrulama yapılmadan nihai akademik etiket gibi sunulmamalıdır.

## Yol haritası

1. NLP için 300–500 kayıtlık manuel doğrulama örneklemi ve macro-F1 değerlendirmesi
2. Semantik embedding + benzer şikâyetler + problem kümeleme
3. Aylık trend ve anomali tespiti
4. Ürün/ürün grubu çıkarımı ve kategori × ürün analizi
5. Firma yanıtı öncesi/sonrası duygu değişimi
6. Firma karşılaştırmalı grafikler ve zaman serileri
7. Analiz sonuçlarını filtreli Excel/rapor olarak dışa aktarma
8. Python gerektirmeyen bağımsız Windows paketleme seçeneğini geliştirme
