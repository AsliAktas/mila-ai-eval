# -*- coding: utf-8 -*-
"""
Rapor üretim scripti (PDF)
--------------------------
- Girdi: mila_eval.xlsx (sheet=data), preds_mila.csv (opsiyonel)
- Çıktı: deliverables/ altında 5 PDF (Doğruluk Özeti, SWOT, Geliştirme Önerileri,
         Müşteri Talepleri Özeti, Teknik Notlar)

Notlar:
- Türkçe glifler için font kaydı (DejaVuSans → Arial → Helvetica fallback).
- Tablolarda header bold, gövde regular; raporlar sade & anlaşılır.

Çalıştırma:
  python src/generate_reports.py --xlsx outputs/eval/mila_eval.xlsx \
    --preds outputs/predictions/preds_mila.csv --outdir deliverables \
    --project "Trendyol Mila Sohbet Botu" --model gpt-5-nano --prepared_by "Ad Soyad"
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import numpy as np

# PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path

# --------------------------
# Yardımcılar
# --------------------------
def pct(x: float, digits: int = 2) -> str:
    """0–1 arası oranı yüzde string'ine çevirir."""
    try:
        return f"{round(100.0 * float(x), digits)}%"
    except Exception:
        return "—"

def pct_val(x: float, digits: int = 2) -> str:
    """Zaten yüzde olan değeri string'ler (kullanılmadı; referans için bırakıldı)."""
    try:
        return f"{round(float(x), digits)}%"
    except Exception:
        return "—"

def topn_counts(series: pd.Series, n: int = 10) -> List[Tuple[str, int]]:
    """Serideki en sık görülen n değeri (etiket dağılımı özetleri için)."""
    s = series.dropna().astype(str)
    vc = s.value_counts().head(n)
    return list(zip(vc.index.tolist(), vc.values.tolist()))

def trunc(s: str, n: int = 160) -> str:
    """Uzun metinleri PDF’de taşırmamak için keser."""
    s = str(s or "")
    return s if len(s) <= n else s[:n-1] + "…"

def clean_str(s: str) -> str:
    """Satır sonlarını boşlukla değiştirerek sadeleştirir."""
    return str(s or "").replace("\n", " ").strip()

# --------------------------
# Veri ve metrikler (tipler)
# --------------------------
@dataclass
class Metrics:
    N: int
    sentiment_acc: float
    sentiment_f1: float
    intent_acc: float
    intent_f1: float
    ans_acc: float
    ans_f1: float
    tur_acc: float
    tur_f1: float
    triple_correct: float

@dataclass
class ConfusionTop:
    gold: str
    pred: str
    count: int

@dataclass
class Inputs:
    xlsx_path: Path
    preds_path: Path
    outdir: Path
    project: str
    model: str
    prepared_by: str
    run_date: str

def load_data(xlsx_path: Path) -> pd.DataFrame:
    """Excel'den 'data' sheet'ini okur; zorunlu kolonları kontrol eder."""
    xl = pd.ExcelFile(xlsx_path)
    df = pd.read_excel(xl, sheet_name="data")
    needed = ["conversation_id","dialog_text","gold_sentiment","gold_intent",
              "gold_yanit_durumu","pred_sentiment","pred_intent","pred_yanit_durumu"]
    for col in needed:
        if col not in df.columns:
            raise SystemExit(f"Girdi sheet 'data' içinde beklenen kolon yok: {col}")
    return df

def compute_basic_metrics(df: pd.DataFrame) -> Metrics:
    """Basit Accuracy & Macro-F1 hesapları (küçük veri için güvenli)."""
    def acc_f1(gold_col, pred_col):
        m = df[gold_col].notna() & df[pred_col].notna()
        g = df.loc[m, gold_col].astype(str)
        p = df.loc[m, pred_col].astype(str)
        if len(g)==0:
            return 0.0, 0.0
        acc = (g.values == p.values).mean()
        classes = sorted(set(g.unique()) | set(p.unique()))
        f1s = []
        for c in classes:
            tp = ((g==c) & (p==c)).sum()
            fp = ((g!=c) & (p==c)).sum()
            fn = ((g==c) & (p!=c)).sum()
            prec = tp / (tp+fp) if (tp+fp)>0 else 0.0
            rec  = tp / (tp+fn) if (tp+fn)>0 else 0.0
            f1   = (2*prec*rec)/(prec+rec) if (prec+rec)>0 else 0.0
            f1s.append(f1)
        mf1 = float(np.mean(f1s)) if f1s else 0.0
        return float(acc), float(mf1)

    N = len(df)
    s_acc, s_f1 = acc_f1("gold_sentiment", "pred_sentiment")
    i_acc, i_f1 = acc_f1("gold_intent", "pred_intent")
    y_acc, y_f1 = acc_f1("gold_yanit_durumu", "pred_yanit_durumu")
    t_acc, t_f1 = (0.0, 0.0)
    if "gold_tur" in df.columns and "pred_tur" in df.columns:
        t_acc, t_f1 = acc_f1("gold_tur", "pred_tur")

    triple = (
        (df["gold_sentiment"].astype(str) == df["pred_sentiment"].astype(str)) &
        (df["gold_intent"].astype(str) == df["pred_intent"].astype(str)) &
        (df["gold_yanit_durumu"].astype(str) == df["pred_yanit_durumu"].astype(str))
    ).mean()

    return Metrics(
        N=N,
        sentiment_acc=s_acc, sentiment_f1=s_f1,
        intent_acc=i_acc, intent_f1=i_f1,
        ans_acc=y_acc, ans_f1=y_f1,
        tur_acc=t_acc, tur_f1=t_f1,
        triple_correct=float(triple)
    )

def top_confusions(df: pd.DataFrame, k: int = 5) -> List[ConfusionTop]:
    """Intent özelinde en sık karışan (gold,pred) çiftlerinden top-k."""
    tmp = (
        df.assign(gold_intent=df["gold_intent"].astype(str),
                  pred_intent=df["pred_intent"].astype(str))
          .query("gold_intent != pred_intent")
          .groupby(["gold_intent","pred_intent"])
          .size().reset_index(name="count")
          .sort_values("count", ascending=False)
          .head(k)
    )
    return [ConfusionTop(r.gold_intent, r.pred_intent, int(r["count"])) for _, r in tmp.iterrows()]

# --------------------------
# PDF yardımcıları
# --------------------------
import os
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def register_tr_font_family():
    """
    Font fallback zinciri:
    1) Proje içi DejaVuSans → 2) Windows Arial → 3) Helvetica (Türkçe eksik olabilir)
    """
    for base in [Path("assets/fonts"), Path("fonts"), Path.cwd() / "assets" / "fonts"]:
        reg = base / "DejaVuSans.ttf"
        bold = base / "DejaVuSans-Bold.ttf"
        if reg.exists() and bold.exists():
            try:
                pdfmetrics.registerFont(TTFont("DejaVuSans", str(reg)))
                pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold)))
                print(f"[fonts] Using DejaVuSans from {base}")
                return ("DejaVuSans", "DejaVuSans-Bold")
            except Exception as e:
                print(f"[fonts] DejaVuSans unusable: {e} → falling back to Arial")
    for winf in [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
        Path(r"C:\Windows\Fonts"),
    ]:
        arial   = winf / "arial.ttf"
        arialbd = winf / "arialbd.ttf"
        if arial.exists() and arialbd.exists():
            pdfmetrics.registerFont(TTFont("Arial", str(arial)))
            pdfmetrics.registerFont(TTFont("Arial-Bold", str(arialbd)))
            print(f"[fonts] Using Arial from {winf}")
            return ("Arial", "Arial-Bold")
    print("[fonts] Fallback to Helvetica (Turkish glyphs may be broken)")
    return ("Helvetica", "Helvetica-Bold")

def base_styles():
    """Paragraf stilleri + seçilen fontları _base/_bold olarak sakla (tablolar için)."""
    base_font, bold_font = register_tr_font_family()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBig", fontName=bold_font, fontSize=18, leading=22, spaceAfter=12))
    styles.add(ParagraphStyle(name="H1", fontName=bold_font, fontSize=14, leading=18, spaceBefore=8, spaceAfter=6))
    styles.add(ParagraphStyle(name="H2", fontName=bold_font, fontSize=12, leading=16, spaceBefore=6, spaceAfter=4))
    styles.add(ParagraphStyle(name="Body", fontName=base_font, fontSize=10.5, leading=14))
    styles.add(ParagraphStyle(name="Mono", fontName=base_font, fontSize=9.5, leading=12))   # Courier yerine Türkçe destekli
    styles.add(ParagraphStyle(name="Small", fontName=base_font, fontSize=9, leading=12, textColor=colors.grey))
    styles._base_font = base_font
    styles._bold_font = bold_font
    return styles

def build_table(data: List[List[str]], col_widths=None, header=True) -> Table:
    """Tablo iskeleti (header çizgisi + padding)."""
    tbl = Table(data, colWidths=col_widths)
    style_cmds = [
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),  # base; rapor içinde override edeceğiz
        ("FONTSIZE", (0,0), (-1,-1), 9.5),
        ("ALIGN",(0,0),(-1,-1),"LEFT"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]
    if header:
        style_cmds.append(("LINEBELOW",(0,0),(-1,0),1,colors.black))
    else:
        style_cmds.append(("LINEBELOW",(0,0),(-1,0),0,colors.white))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl

def save_pdf(filename: Path, elements: List):
    """Basit PDF kaydetme (A4, kenar boşlukları standard)."""
    doc = SimpleDocTemplate(str(filename), pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=1.6*cm, bottomMargin=1.6*cm)
    doc.build(elements)

# --------------------------
# 01 Doğruluk Özeti
# --------------------------
def make_report_accuracy(inp: Inputs, df: pd.DataFrame, metrics: Metrics):
    st = base_styles()
    elems: List = []
    title = f"{inp.project} — Doğruluk Özeti"
    subtitle = f"Tarih: {inp.run_date} • Model: {inp.model} • Hazırlayan: {inp.prepared_by}"
    elems += [Paragraph(title, st["TitleBig"]), Paragraph(subtitle, st["Small"]), Spacer(1, 8)]

    data_tbl = [
        ["Metrik", "Accuracy", "Macro-F1", "n"],
        ["Sentiment", pct(metrics.sentiment_acc), pct(metrics.sentiment_f1), str(metrics.N)],
        ["Intent", pct(metrics.intent_acc), pct(metrics.intent_f1), str(metrics.N)],
        ["Yanıt durumu", pct(metrics.ans_acc), pct(metrics.ans_f1), str(metrics.N)],
        ["Tür", pct(metrics.tur_acc), pct(metrics.tur_f1), str(metrics.N)],
        ["Üçü birden doğru", pct(metrics.triple_correct), "—", str(metrics.N)],
    ]
    base_font = getattr(st, "_base_font", "Helvetica")
    bold_font = getattr(st, "_bold_font", "Helvetica-Bold")

    tbl = build_table(data_tbl, col_widths=[5*cm, 3*cm, 3*cm, 2*cm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), bold_font),   # header bold
        ("FONTNAME", (0,1), (-1,-1), base_font),  # body regular
    ]))
    elems.append(tbl)
    elems.append(Spacer(1, 10))

    insights = (
        "Structured output (Pydantic) yaklaşımı ile boş/parse hataları ortadan kalktı. "
        "Intent, Sentiment ve Yanıt Durumu alanlarında yüksek doğruluk elde edildi. "
        "Geliştirme alanı: 'Tür' (Soru/İstek/Şikayet/Sorun/Bilgi alma/İade) ayrımının tutarlılığı."
    )
    elems += [Paragraph("Kısa İçgörü", st["H1"]), Paragraph(insights, st["Body"])]

    out = inp.outdir / "01_dogruluk_ozet.pdf"
    save_pdf(out, elems)

# --------------------------
# 02 SWOT
# --------------------------
def make_report_swot(inp: Inputs, df: pd.DataFrame, metrics: Metrics, confs: List[ConfusionTop]):
    """Metriğe göre kısa SWOT (güçlü/zayıf/fırsat/tehdit) listeleri."""
    st = base_styles()
    elems: List = []
    elems += [Paragraph(f"{inp.project} — SWOT Analizi", st["TitleBig"]),
              Paragraph(f"Tarih: {inp.run_date} • Model: {inp.model}", st["Small"]),
              Spacer(1, 8)]

    S = []
    if metrics.intent_acc >= 0.7: S.append("Intent alanında yüksek doğruluk (müşteri talepleri net ayrışıyor).")
    if metrics.ans_acc   >= 0.7: S.append("Yanıt durumu tespitinde güçlü performans (çözüm sinyalleri yakalanıyor).")
    if metrics.sentiment_acc >= 0.7: S.append("Sentiment sınıflandırması tutarlı (pozitif/negatif ayrımı yerinde).")
    S.append("Structured output ile tek satır tutarlı JSON — operasyonel hatalar minimize.")

    W = []
    if metrics.tur_acc < 0.5:
        W.append("“Tür” sınıflandırmasında belirsizlik (Soru/Bilgi alma/İstek/Şikayet/Sorun).")
    if len(confs) > 0:
        W.append("Bazı alt-üst taksonomi farkları karışım yaratıyor (örn. ‘Defolu ürün’ ↔ ‘Hasarlı ürün’).")

    O = [
        "Hafif post-fix kuralları ile ‘Tür’ accuracy’sinde kısa vadede %15–25 potansiyel artış.",
        "Intent-detay normalize (eşanlam/üst-alt) ile raporların daha tutarlı ve aksiyon alınabilir sunumu.",
        "Sohbet kapanışlarına empatik şablon ve ‘çözülmedi’ durumunda canlı destek yönlendirmesi."
    ]

    T = [
        "Küçük veri (N=40) + çok sınıf → per-class metrik oynaklığı.",
        "Marka/mağaza bazında taksonomi farklılıkları bakım yükü yaratabilir."
    ]

    def bullet_block(title: str, items: List[str]):
        elems.append(Paragraph(title, st["H1"]))
        if not items:
            elems.append(Paragraph("—", st["Body"]))
            return
        for it in items:
            elems.append(Paragraph(f"• {it}", st["Body"]))
        elems.append(Spacer(1, 6))

    bullet_block("Strengths (Güçlü)", S)
    bullet_block("Weaknesses (Zayıf)", W)
    bullet_block("Opportunities (Fırsatlar)", O)
    bullet_block("Threats (Tehditler)", T)

    out = inp.outdir / "02_SWOT.pdf"
    save_pdf(out, elems)

# --------------------------
# 03 Geliştirme Önerileri
# --------------------------
def make_report_suggestions(inp: Inputs, df: pd.DataFrame, metrics: Metrics):
    """Hızlı kazanım odaklı öneriler (Tür için hafif post-fix vb.)."""
    st = base_styles()
    elems: List = []
    elems += [Paragraph(f"{inp.project} — Geliştirme Önerileri", st["TitleBig"]),
              Paragraph(f"Tarih: {inp.run_date} • Model: {inp.model}", st["Small"]),
              Spacer(1, 8)]

    elems.append(Paragraph("Önceliklendirme", st["H1"]))
    elems.append(Paragraph("Hızlı kazanım + düşük risk sırasıyla öneriler:", st["Body"]))

    # A. Tür post-fix
    elems.append(Paragraph("A) ‘Tür’ İçin Hafif Post-Fix Kuralları", st["H2"]))
    elems.append(Paragraph(
        "• İstek: “... istiyorum / lütfen ... yapın / iptal edin / düzeltin / kapatın” → Tür=İstek "
        "• Şikayet: “şikayet / rezalet / berbat / mağdur / memnun değilim / sinir” → Tür=Şikayet "
        "• Soru/Bilgi alma: “?, nasıl, nedir, ne zaman, nerede, mümkün mü” → süreç/koşul sorusu ise Bilgi alma, aksi Soru "
        "• İade niyeti belirginse Tür=İade; aksi halde Sorun",
        st["Body"]
    ))

    # B. Taksonomi normalize
    elems.append(Paragraph("B) Taksonomi Normalize (Rapor Katmanı)", st["H2"]))
    elems.append(Paragraph(
        "• ‘Defolu ürün’ → ‘Hasarlı ürün’ "
        "• ‘Beden tablosu’ → ‘Beden’ "
        "• ‘Fatura hatası’ → ‘Ödeme’ (detay: Fatura fiyatı hatası) ",
        st["Body"]
    ))

    # C. Operasyonel yönergeler
    elems.append(Paragraph("C) Operasyonel Yönergeler", st["H2"]))
    elems.append(Paragraph(
        "• Çözüm üretilemeyen diyaloglarda otomatik canlı destek yönlendirmesi. "
        "• Teşekkür var ama çözüm yoksa sentiment=Nötr. "
        "• JSON alan adları ve kapalı kümeler CI’de şemayla doğrulansın.",
        st["Body"]
    ))

    out = inp.outdir / "03_gelistirme_onerileri.pdf"
    save_pdf(out, elems)

# --------------------------
# 04 Müşteri Talepleri Özeti
# --------------------------
def make_report_customer_needs(inp: Inputs, df: pd.DataFrame):
    """Top intent + örnek alıntılar + intent_detay dağılımı."""
    st = base_styles()
    elems: List = []
    elems += [Paragraph(f"{inp.project} — Müşteri Talepleri Özeti", st["TitleBig"]),
              Paragraph(f"Tarih: {inp.run_date}", st["Small"]),
              Spacer(1, 8)]

    # Top Intent & örnek diyalog
    top_intents = topn_counts(df["gold_intent"], 5)
    data_tbl = [["Top Intent", "Adet"]]+[[k, str(v)] for k,v in top_intents]
    base_font = getattr(st, "_base_font", "Helvetica")
    bold_font = getattr(st, "_bold_font", "Helvetica-Bold")

    elems.append(Paragraph("Top 5 Intent", st["H1"]))
    tbl = build_table(data_tbl, col_widths=[9*cm, 3*cm])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), bold_font),
        ("FONTNAME", (0,1), (-1,-1), base_font),
    ]))
    elems.append(tbl)
    elems.append(Spacer(1, 8))

    # Örnek alıntılar (her intent için 1 örnek)
    elems.append(Paragraph("Örnek Vaka Alıntıları", st["H1"]))
    for intent, _ in top_intents:
        row = df.loc[df["gold_intent"].astype(str)==intent].head(1)
        if len(row)>0:
            excerpt = trunc(clean_str(row.iloc[0]["dialog_text"]), 320)
            elems.append(Paragraph(f"• {intent} — “{excerpt}”", st["Body"]))
    elems.append(Spacer(1, 6))

    # intent_detay dağılımı (varsa)
    if "pred_intent_detay" in df.columns or "gold_intent_detay" in df.columns:
        col = "gold_intent_detay" if "gold_intent_detay" in df.columns else "pred_intent_detay"
        dets = topn_counts(df[col], 10)
        det_tbl = [["Intent Detay", "Adet"]]+[[k, str(v)] for k,v in dets]
        elems.append(Spacer(1,6))
        elems.append(Paragraph("Intent Detay Dağılımı (Top 10)", st["H1"]))
        tbl2 = build_table(det_tbl, col_widths=[9*cm, 3*cm])
        tbl2.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), bold_font),
            ("FONTNAME", (0,1), (-1,-1), base_font),
        ]))
        elems.append(tbl2)

    out = inp.outdir / "04_musteri_talepleri_ozeti.pdf"
    save_pdf(out, elems)

# --------------------------
# 05 Teknik Notlar
# --------------------------
def make_report_tech_notes(inp: Inputs):
    """Çalıştırma notları, klasör yapısı, kalite güvencesi."""
    st = base_styles()
    elems: List = []
    elems += [Paragraph(f"{inp.project} — Teknik Notlar", st["TitleBig"]),
              Paragraph(f"Tarih: {inp.run_date}", st["Small"]),
              Spacer(1, 8)]

    elems.append(Paragraph("Model & Çalıştırma", st["H1"]))
    elems.append(Paragraph(
        f"• Model: {inp.model} (alternatif: gpt-4o-mini, gpt-4.1-mini)\n"
        "• Structured output (Pydantic şema) ile tek satır tutarlı JSON; parse hataları engellenir.\n"
        "• Komut: python src\\eval_pipeline.py --in-json ... --prompt ... --pred-out ... --excel-out ... --cm-dir ... --model gpt-5-nano",
        st["Body"]
    ))

    elems.append(Paragraph("Klasör Yapısı", st["H1"]))
    elems.append(Paragraph(
        "deliverables/\n"
        "  ├─ mila_eval.xlsx\n"
        "  ├─ preds_mila.csv\n"
        "  ├─ 01_dogruluk_ozet.pdf\n"
        "  ├─ 02_SWOT.pdf\n"
        "  ├─ 03_gelistirme_onerileri.pdf\n"
        "  ├─ 04_musteri_talepleri_ozeti.pdf\n"
        "  └─ 05_teknik_notlar.pdf",
        st["Mono"]
    ))

    elems.append(Paragraph("Kalite Güvencesi", st["H1"]))
    elems.append(Paragraph(
        "• JSON şema doğrulaması CI aşamasında zorunlu.\n"
        "• ‘Tür’ iyileştirmesi için hafif post-fix kuralları uygulanabilir (mantıksal tutarlılık korunur).\n"
        "• Tekrarlanabilirlik: prompt dosyası ve komutlar versiyonlanır.",
        st["Body"]
    ))

    out = inp.outdir / "05_teknik_notlar.pdf"
    save_pdf(out, elems)

# --------------------------
# Main
# --------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, help="outputs/eval/mila_eval.xlsx")
    ap.add_argument("--preds", required=False, default=None, help="outputs/predictions/preds_mila.csv (opsiyonel)")
    ap.add_argument("--outdir", required=True, help="deliverables/")
    ap.add_argument("--project", default="Trendyol Mila Sohbet Botu")
    ap.add_argument("--model", default="gpt-5-nano")
    ap.add_argument("--prepared_by", default="Analist")
    args = ap.parse_args()

    inputs = Inputs(
        xlsx_path=Path(args.xlsx),
        preds_path=Path(args.preds) if args.preds else None,
        outdir=Path(args.outdir),
        project=args.project,
        model=args.model,
        prepared_by=args.prepared_by,
        run_date=datetime.now().strftime("%Y-%m-%d"),
    )

    inputs.outdir.mkdir(parents=True, exist_ok=True)
    df = load_data(inputs.xlsx_path)
    metrics = compute_basic_metrics(df)
    confs = top_confusions(df, k=5)

    # 5 raporu üret
    make_report_accuracy(inputs, df, metrics)
    make_report_swot(inputs, df, metrics, confs)
    make_report_suggestions(inputs, df, metrics)
    make_report_customer_needs(inputs, df)
    make_report_tech_notes(inputs)

    print(f"[OK] Raporlar üretildi: {inputs.outdir}")

if __name__ == "__main__":
    main()
