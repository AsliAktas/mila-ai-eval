# -*- coding: utf-8 -*-
"""
Uçtan uca değerlendirme pipeline'ı
----------------------------------
Adımlar:
  1) JSON/JSONL veri setini yükle (load_conversations)
  2) Allowed intent listesini hazırla (gold'a göre)
  3) LLM tahminlerini üret ve CSV'ye yaz (predict_conversations)
  4) Gold + pred birleştir
  5) Excel ve confusion çıktıları oluştur (write_excel_report, save_confusions)

Örnek:
  python src/eval_pipeline.py --in-json data/raw/20-sohbet-trendyol-mila.json \
    --prompt src/prompt_template.txt \
    --pred-out outputs/predictions/preds_mila.csv \
    --excel-out outputs/eval/mila_eval.xlsx \
    --cm-dir outputs/eval/confusions \
    --model gpt-5-nano
"""
import argparse
from pathlib import Path
import pandas as pd

from data_load import load_conversations, build_allowed_intents
from llm_infer import predict_conversations
from metrics_eval import write_excel_report, save_confusions

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-json", required=True, help="data/raw/20-sohbet-trendyol-mila.json")
    ap.add_argument("--prompt", default="src/prompt_template.txt")
    ap.add_argument("--pred-out", default="outputs/predictions/preds_mila.csv")
    ap.add_argument("--excel-out", default="outputs/eval/mila_eval.xlsx")
    ap.add_argument("--cm-dir", default="outputs/eval/confusions")
    ap.add_argument("--model", default=None, help="gpt-5-nano | gpt-4o-mini | gpt-4.1-mini")
    args = ap.parse_args()

    # 1) Load data
    df = load_conversations(args.in_json)

    # 2) Allowed intents (gold set)
    intents = build_allowed_intents(df)

    # 3) Predict (Structured Output; boşsa SystemExit ile durur)
    predict_conversations(
        df_convs=df,
        prompt_template_path=args.prompt,
        intents=intents,
        out_path=args.pred_out,
        model_override=args.model,
    )

    # 4) Merge gold + preds
    pred = pd.read_csv(args.pred_out)
    merged = df.merge(pred, on="conversation_id", how="left")

    # 5) Reports
    write_excel_report(merged, args.excel_out)
    save_confusions(merged, args.cm_dir)

if __name__ == "__main__":
    main()
