# ACME Müşteri Memnuniyeti Analiz Aracı

    ## 1. Proje Hakkında
    Bu proje, e-ticaret müşteri hizmetleri sohbetlerini yapay zeka kullanarak otomatik olarak sınıflandırmak ve analiz etmek için tasarlanmış bir araçtır. Geliştirilen model, müşteri niyetini, duygusunu ve sorun türünü anlamaya odaklanır. Projenin temel amacı, büyük hacimli müşteri sohbetlerini anlamlandırarak operasyonel verimliliği artırmak ve müşteri memnuniyetini yükseltmektir.

    ## 2. Kullanılan Kaynaklar
    Bu projede, veri analizi ve model geliştirme süreçlerinde çeşitli kaynaklar kullanılmıştır:

    * **Sohbet Verileri**: `trendyol_mila.xlsx` dosyası, manuel olarak etiketlenmiş müşteri hizmetleri sohbetlerini içerir ve modelin eğitimi ile doğruluğunun değerlendirilmesi için ground truth verisi olarak kullanılmıştır.
    * **Model ve API**: E-ticaret sohbetlerinin sınıflandırılması için, **Groq**'un düşük gecikmeli **Llama 3** ailesi modelleri kullanılmıştır.
    * **Analiz Raporu**: `ACME MMA.pdf` raporu, projenin başlangıç noktası ve problem tanımı için temel bir kaynak görevi görmüştür. Raporda, "Teslimat sorunları", "İade/değişim süreçleri" ve "Sistem/teknoloji sorunları" gibi ana kök nedenler belirlenmiştir.

    ## 3. Çalışma Şekli
    Proje, **anlam öncelikli sınıflandırma** yaklaşımını benimser. Anahtar kelimelerden ziyade, sohbetin bütününde yer alan bağlam ve gerçek niyet dikkate alınır.

    ### Sınıflandırma Alanları
    Model, her bir sohbeti beş farklı kategoriye göre etiketler:
    * `yanit_durumu` (Çözüldü/Çözülemedi)
    * `sentiment` (Pozitif/Negatif/Nötr)
    * `tur` (Şikayet, Sorun, Bilgi alma, İstek, Soru, İade)
    * `intent` (Asıl amaç, ör: Kargo, Ödeme vb.)
    * `intent_detay` (Daha spesifik durum)

    ### Tahmin ve Değerlendirme
    Model, her bir sohbet için tek bir satır JSON çıktısı üretir. Bu çıktılar, `calculate_accuracy.py` betiği ile ground truth verisiyle karşılaştırılarak her bir kategorinin doğruluğu hesaplanır.

    ## 4. Performans ve Doğruluk
    Projenin ilk denemesinde elde edilen doğruluk oranları aşağıdadır. Bu veriler, modelin güçlü ve zayıf yönlerini göstermektedir.

    | Kategori | Model Tahmin Doğruluğu (%) |
    | :--- | :---: |
    | Yanıt Durumu | %100.00 |
    | Sentiment | %67.50 |
    | Tür | %55.00 |
    | Intent | %52.50 |
    | Intent Detay | %7.50 |
    | **Genel (Tam Eşleşme)** | **%5.00** |

    ### Analiz
    * **Güçlü Yönler:** Model, bir sorunun çözülüp çözülmediğini belirlemede mükemmeldir.
    * **Zayıf Yönler:** `Tür`, `Intent` ve `Intent Detay` gibi konuşmanın içeriğine dayalı etiketlemelerde ciddi zorluklar yaşanmaktadır. Özellikle `Intent Detay` doğruluğunun çok düşük olması, modelin ince ayrıntıları yakalamakta başarısız olduğunu gösterir.

    ## 5. Gelecek İyileştirmeler
    Elde edilen sonuçlara dayanarak, projenin genel doğruluğunu artırmak için aşağıdaki adımlar planlanmaktadır:

    * **Prompt Optimizasyonu**: `Tür` ve `Intent` kategorileri arasındaki nüansları daha iyi açıklayan yeni, daha detaylı örnekler içeren bir prompt şablonu oluşturulacaktır.
    * **Daha Fazla Örnek Veri**: Modelin zorlandığı senaryolar için ek etiketli veri sağlanarak modelin öğrenme yeteneği artırılacaktır.
    * **Model Seçimi**: Daha karmaşık ve nüans gerektiren görevler için **Llama 3** gibi daha güçlü modellerin kullanılması düşünülmektedir.

    ---

    ### Nasıl Çalıştırılır?

    Projeyi yerel makinenizde çalıştırmak için terminalde aşağıdaki komutları kullanabilirsiniz:

    ```bash
    # Gerekli Python kütüphanelerini yükleyin
    pip install -r requirements.txt

    # .env dosyasında Groq API anahtarınızı tanımlayın
    # GROQ_API_KEY="...apikey..."

    # LLM tahminlerini çalıştırın
    python src/llm_infer.py --in-xlsx "outputs/trendyol_mila_updated.xlsx" --sheet-name "sohbetler_GUNCEL" --out "outputs/preds_mila_turfix.csv" --model "llama-3.1-70b-versatile"

    # Doğruluk hesaplamasını yapın
    python src/calculate_accuracy.py
    