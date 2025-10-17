import json
import pandas as pd
import os

# 'trendyol_mila.xlsx' dosyasının içindeki 'sohbetler' sayfasını okuma
df_truth = pd.read_excel(os.path.join('outputs', 'trendyol_mila.xlsx'), sheet_name='sohbetler')

# 'preds_mila_turfix.csv' dosyasını okuma (Bu satır doğru)
df_preds = pd.read_csv(os.path.join('outputs', 'preds_mila_turfix.csv'))

# Kolon isimlerini birleştirme için eşitleme
df_preds = df_preds.rename(columns={'conversation_id': 'sohbet_id'})

# Tahmin JSON'larını ayrıştırma ve yeni sütunlar oluşturma
def parse_prediction(pred_json):
    try:
        data = json.loads(pred_json)
        return pd.Series({
            'pred_yanit_durumu': data.get('yanit_durumu'),
            'pred_sentiment': data.get('sentiment'),
            'pred_tur': data.get('tur'),
            'pred_intent': data.get('intent'),
            'pred_intent_detay': data.get('intent_detay')
        })
    except json.JSONDecodeError:
        return pd.Series({
            'pred_yanit_durumu': None,
            'pred_sentiment': None,
            'pred_tur': None,
            'pred_intent': None,
            'pred_intent_detay': None
        })

# 'prediction' sütunundaki JSON verisini yeni sütunlara dönüştür
# Eğer prediction sütununuz yoksa ve doğrudan JSON objesi varsa,
# 'df_preds' yerine doğrudan JSON'a apply yapabilirsiniz.
if 'prediction' in df_preds.columns:
    parsed_preds = df_preds['prediction'].apply(parse_prediction)
    df_preds = pd.concat([df_preds, parsed_preds], axis=1)

# Verileri sohbet_id üzerinden birleştirme
df_merged = pd.merge(df_truth, df_preds, on='sohbet_id', how='inner')

# Accuracy (Doğruluk) hesaplama
total_conversations = len(df_merged)

# Her bir kategori için doğruluk hesaplama
yanit_durumu_accuracy = (df_merged['yanit_durumu'] == df_merged['pred_yanit_durumu']).mean() * 100
sentiment_accuracy = (df_merged['sentiment'] == df_merged['pred_sentiment']).mean() * 100
tur_accuracy = (df_merged['tur'] == df_merged['pred_tur']).mean() * 100
intent_accuracy = (df_merged['intent'] == df_merged['pred_intent']).mean() * 100
intent_detay_accuracy = (df_merged['intent_detay'] == df_merged['pred_intent_detay']).mean() * 100

# Toplam doğruluk (tüm etiketlerin aynı olduğu durum)
all_correct = (
    (df_merged['yanit_durumu'] == df_merged['pred_yanit_durumu']) &
    (df_merged['sentiment'] == df_merged['pred_sentiment']) &
    (df_merged['tur'] == df_merged['pred_tur']) &
    (df_merged['intent'] == df_merged['pred_intent']) &
    (df_merged['intent_detay'] == df_merged['pred_intent_detay'])
)
overall_accuracy = all_correct.mean() * 100

# Sonuçları yazdırma
print("--- Sınıflandırma Doğruluk Oranları ---")
print(f"Toplam sohbet sayısı: {total_conversations}")
print(f"Yanıt Durumu Doğruluğu: %{yanit_durumu_accuracy:.2f}")
print(f"Sentiment Doğruluğu: %{sentiment_accuracy:.2f}")
print(f"Tür Doğruluğu: %{tur_accuracy:.2f}")
print(f"Intent Doğruluğu: %{intent_accuracy:.2f}")
print(f"Intent Detay Doğruluğu: %{intent_detay_accuracy:.2f}")
print("-" * 35)
print(f"Tüm etiketlerin tam olarak doğru olduğu genel doğruluk: %{overall_accuracy:.2f}")