# -*- coding: utf-8 -*-
"""
Metrik hesapları ve Excel/Confusion çıktıları.

- Excel: iki sheet üretir
  - data: birleşik (gold+pred) satırlar
  - metrics: beş alan için accuracy & macro-F1 + triple_correct
- Confusion CSV'leri: belirtilen klasöre, alan bazında (sentiment/intent/yanit_durumu/tur/intent_detay)

Kullanım (pipeline içinden):
  write_excel_report(merged_df, "outputs/eval/mila_eval.xlsx")
  save_confusions(merged_df, "outputs/eval/confusions")
"""
from __future__ import annotations
from pathlib import Path
from typing import Tuple, List, Dict
import numpy as np
import pandas as pd

# ---------- temel hesaplar ----------
def _acc_f1(y_true: pd.Series, y_pred: pd.Series) -> Tuple[float, float]:
    """
    Accuracy + Macro-F1 (küçük veri için güvenli manuel hesap).
    NaN'leri dışarıda bırakır.
    """
    yt = pd.Series(y_true).dropna().astype(str)
    yp = pd.Series(y_pred).dropna().astype(str)
    if len(yt) == 0 or len(yp) == 0:
        return 0.0, 0.0
    # hizalama (varsayımsal: indeksler zaten aynı merged df'de)
    n = min(len(yt), len(yp))
    yt = yt.iloc[:n]
    yp = yp.iloc[:n]
    acc = (yt.values == yp.values).mean()

    classes = sorted(set(yt.unique()) | set(yp.unique()))
    f1s: List[float] = []
    for c in classes:
        tp = ((yt == c) & (yp == c)).sum()
        fp = ((yt != c) & (yp == c)).sum()
        fn = ((yt == c) & (yp != c)).sum()
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1   = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        f1s.append(f1)
    mf1 = float(np.mean(f1s)) if f1s else 0.0
    return float(acc), mf1

# ---------- Excel raporu ----------
def write_excel_report(df_merged: pd.DataFrame, out_xlsx: str) -> None:
    """
    'df_merged' genellikle gold/pred kolonlarını içerir.
    Excel içine:
      - data sheet: df_merged aynen
      - metrics sheet: accuracy & macroF1 (5 alan) + triple_correct
    """
    Path(out_xlsx).parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict] = []
    for label, gcol, pcol in [
        ("sentiment", "gold_sentiment", "pred_sentiment"),
        ("intent", "gold_intent", "pred_intent"),
        ("yanit_durumu", "gold_yanit_durumu", "pred_yanit_durumu"),
        ("tur", "gold_tur", "pred_tur"),
        ("intent_detay", "gold_intent_detay", "pred_intent_detay"),
    ]:
        if gcol in df_merged.columns and pcol in df_merged.columns:
            acc, mf1 = _acc_f1(df_merged[gcol], df_merged[pcol])
            rows += [
                {"metric": f"accuracy_{label}", "value": acc},
                {"metric": f"macroF1_{label}", "value": mf1},
            ]

    # üçü birden doğru (sentiment+intent+yanıt_durumu)
    if all(c in df_merged.columns for c in [
        "gold_sentiment", "pred_sentiment",
        "gold_intent", "pred_intent",
        "gold_yanit_durumu", "pred_yanit_durumu"
    ]):
        triple = (
            (df_merged["gold_sentiment"].astype(str) == df_merged["pred_sentiment"].astype(str)) &
            (df_merged["gold_intent"].astype(str) == df_merged["pred_intent"].astype(str)) &
            (df_merged["gold_yanit_durumu"].astype(str) == df_merged["pred_yanit_durumu"].astype(str))
        ).mean()
        rows.append({"metric": "triple_correct", "value": float(triple)})

    metrics_df = pd.DataFrame(rows)

    with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as wr:
        df_merged.to_excel(wr, sheet_name="data", index=False)
        metrics_df.to_excel(wr, sheet_name="metrics", index=False)
    print(f"[OK] Excel rapor: {out_xlsx}")

# ---------- Confusion tabloları ----------
def _confusion_counts(df: pd.DataFrame, gcol: str, pcol: str) -> pd.DataFrame:
    if gcol not in df.columns or pcol not in df.columns:
        return pd.DataFrame(columns=["gold", "pred", "count"])
    tmp = (df.assign(
              _g=df[gcol].astype(str),
              _p=df[pcol].astype(str)
           )
           .query("_g != _p")
           .groupby(["_g", "_p"]).size()
           .reset_index(name="count")
           .rename(columns={"_g": "gold", "_p": "pred"})
           .sort_values("count", ascending=False))
    return tmp

def save_confusions(df_merged: pd.DataFrame, out_dir: str) -> None:
    """
    Alan bazında basit confusion CSV'leri üretir.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    specs = [
        ("sentiment", "gold_sentiment", "pred_sentiment"),
        ("intent", "gold_intent", "pred_intent"),
        ("yanit_durumu", "gold_yanit_durumu", "pred_yanit_durumu"),
        ("tur", "gold_tur", "pred_tur"),
        ("intent_detay", "gold_intent_detay", "pred_intent_detay"),
    ]
    for name, gcol, pcol in specs:
        dfc = _confusion_counts(df_merged, gcol, pcol)
        path = out / f"confusion_{name}.csv"
        dfc.to_csv(path, index=False, encoding="utf-8")
        print(f"[OK] Confusion saved: {path}")
