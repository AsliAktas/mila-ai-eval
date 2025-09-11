⚙️ Çalıştırma
<details> <summary><strong>macOS / Linux</strong></summary>
python src/eval_pipeline.py \
  --in-json data/raw/20-sohbet-trendyol-mila.json \
  --prompt src/prompt_template.txt \
  --pred-out outputs/predictions/preds_mila.csv \
  --excel-out outputs/eval/mila_eval.xlsx \
  --cm-dir outputs/eval/confusions \
  --model gpt-5-nano

</details> <details> <summary><strong>Windows PowerShell</strong></summary>
python src/eval_pipeline.py `
  --in-json data/raw/20-sohbet-trendyol-mila.json `
  --prompt src/prompt_template.txt `
  --pred-out outputs/predictions/preds_mila.csv `
  --excel-out outputs/eval/mila_eval.xlsx `
  --cm-dir outputs/eval/confusions `
  --model gpt-5-nano

</details> <details> <summary><strong>Windows CMD</strong></summary>
python src\eval_pipeline.py ^
  --in-json data\raw\20-sohbet-trendyol-mila.json ^
  --prompt src\prompt_template.txt ^
  --pred-out outputs\predictions\preds_mila.csv ^
  --excel-out outputs\eval\mila_eval.xlsx ^
  --cm-dir outputs\eval\confusions ^
  --model gpt-5-nano

</details>
📄 PDF Raporları
python src/generate_reports.py \
  --xlsx outputs/eval/mila_eval.xlsx \
  --preds outputs/predictions/preds_mila.csv \
  --outdir deliverables \
  --project "Trendyol Mila Sohbet Botu" \
  --model gpt-5-nano \
  --prepared_by "Aslı Aktaş"

📦 Teslim Paketi
python src/package_deliverables.py --dir deliverables --out mila-deliverables

🧵 Girdi Formatı (JSON / JSONL)

conversation_id (yoksa indeks)

dialog_text (yoksa messages/turns → otomatik derlenir)

gold_* (opsiyonel): gold_sentiment, gold_intent, gold_yanit_durumu, gold_tur, gold_intent_detay

Zaman alanları (opsiyonel): sohbet_baslangic, sohbet_bitis → Excel/data’da süre kolonları

Alternatif örnek

{
  "conversation_id": "abc-123",
  "messages": [
    {"role": "user", "text": "Kargom nerede?"},
    {"role": "assistant", "text": "Takip linki ..."}
  ]
}
