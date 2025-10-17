import os
import json
import pandas as pd
import matplotlib.pyplot as plt

def create_readme_file():
    readme_content = """# ACME Müşteri Memnuniyeti Analiz Aracı

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
    """
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print("README.md dosyası oluşturuldu.")

def create_eda_notebook():
    notebook_content = {
    "cells": [
    {
    "cell_type": "markdown",
    "metadata": {},
    "source": ["# Müşteri Sohbeti Sınıflandırma Analizi\n",
    "Bu notebook, LLM modelimizin tahminlerinin doğruluğunu görselleştirmek için hazırlanmıştır."]
    },
    {
    "cell_type": "code",
    "metadata": {},
    "source": [
    "import pandas as pd\n",
    "import json\n",
    "import matplotlib.pyplot as plt\n",
    "import os"
    ]
    },
    {
    "cell_type": "code",
    "metadata": {},
    "source": [
    "# Veri setlerini yükle\n",
    "df_truth = pd.read_csv(os.path.join('outputs', 'trendyol_mila.xlsx - sohbetler.csv'))\n",
    "df_preds = pd.read_csv(os.path.join('outputs', 'preds_mila_turfix.csv'))\n\n",
    "print('Veriler başarıyla yüklendi.')"
    ]
    },
    {
    "cell_type": "code",
    "metadata": {},
    "source": [
    "# Tahmin JSON'larını ayrıştırma ve yeni sütunlar oluşturma\n",
    "def parse_prediction(pred_json):\n",
    "    try:\n",
    "        data = json.loads(pred_json)\n",
    "        return pd.Series({\n",
    "            'pred_yanit_durumu': data.get('yanit_durumu'),\n",
    "            'pred_sentiment': data.get('sentiment'),\n",
    "            'pred_tur': data.get('tur'),\n",
    "            'pred_intent': data.get('intent'),\n",
    "            'pred_intent_detay': data.get('intent_detay')\n",
    "        })\n",
    "    except json.JSONDecodeError:\n",
    "        return pd.Series({})\n\n",
    "# Kolon isimlerini birleştirme için eşitleme\n",
    "df_preds = df_preds.rename(columns={'conversation_id': 'sohbet_id'})\n\n",
    "# Eğer 'prediction' sütunu varsa JSON'u ayrıştır\n",
    "if 'prediction' in df_preds.columns:\n",
    "    parsed_preds = df_preds['prediction'].apply(parse_prediction)\n",
    "    df_preds = pd.concat([df_preds, parsed_preds], axis=1)\n\n",
    "# Verileri sohbet_id üzerinden birleştirme\n",
    "df_merged = pd.merge(df_truth, df_preds, on='sohbet_id', how='inner')\n\n",
    "print('Veri setleri birleştirildi ve tahminler ayrıştırıldı.')"
    ]
    },
    {
    "cell_type": "code",
    "metadata": {},
    "source": [
    "# Doğruluk (Accuracy) hesaplama\n",
    "categories = ['yanit_durumu', 'sentiment', 'tur', 'intent', 'intent_detay']\n",
    "accuracies = []\n\n",
    "for category in categories:\n",
    "    pred_col = f'pred_{category}'\n",
    "    accuracy = (df_merged[category] == df_merged[pred_col]).mean() * 100\n",
    "    accuracies.append(accuracy)\n\n",
    "print('Doğruluk oranları hesaplandı.')\n",
    "print(accuracies)"
    ]
    },
    {
    "cell_type": "code",
    "metadata": {},
    "source": [
    "# Sonuçları görselleştirme\n",
    "plt.figure(figsize=(10, 6))\n",
    "plt.bar(categories, accuracies, color=['green', 'blue', 'orange', 'red', 'purple'])\n",
    "plt.title('Kategori Bazında Doğruluk Oranları (LLM vs Ground Truth)', fontsize=16)\n",
    "plt.ylabel('Doğruluk (%)', fontsize=12)\n",
    "plt.xlabel('Kategori', fontsize=12)\n",
    "plt.ylim(0, 100)\n",
    "plt.grid(axis='y', linestyle='--', alpha=0.7)\n\n",
    "for i, v in enumerate(accuracies):\n",
    "    plt.text(i, v + 2, f'{v:.2f}%', ha='center', fontsize=10)\n\n",
    "plt.tight_layout()\n",
    "plt.savefig('outputs/accuracy_comparison.png')\n",
    "plt.show()"
    ]
    }
    ],
    "metadata": {
    "kernelspec": {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3"
    },
    "language_info": {
    "codemirror_mode": {
    "name": "ipython",
    "version": 3
    },
    "file_extension": ".py",
    "mimetype": "text/x-python",
    "name": "python",
    "nbconvert_exporter": "python",
    "pygments_lexer": "ipython3",
    "version": "3.10"
    }
    },
    "nbformat": 4,
    "nbformat_minor": 4
    }

    if not os.path.exists('notebooks'):
        os.makedirs('notebooks')

    with open(os.path.join('notebooks', 'EDA.ipynb'), 'w', encoding='utf-8') as f:
        json.dump(notebook_content, f, indent=4)
    print("EDA.ipynb dosyası 'notebooks' klasöründe oluşturuldu.")
def main():
    if not os.path.exists('outputs'):
        os.makedirs('outputs')

create_readme_file()
create_eda_notebook()
main()