# -*- coding: utf-8 -*-
"""
Veri yükleme yardımcıları.

- load_conversations(in_json): model girişleri ve gold etiketleriyle DataFrame üretir.
  Zaman bilgisi kolonları (sohbet_baslangic, sohbet_bitis, toplam_sure_saniye) eklenir (varsa parse edilir).
- build_allowed_intents(df): gold_intent kolonundan izinli intent listesini üretir (fallback sabit liste).

Not:
  Verinizin alan isimleri farklı olabilir; 'dialog_text', 'conversation_id', 'gold_*' alanları yoksa
  makul varsayılanlarla doldurulur (boş/NaN kalabilir). Pipeline bu durumda yine çalışır.
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Any, Dict
import json
from datetime import datetime
import pandas as pd

# Bu sabit liste, gold_intent yoksa fallback olarak kullanılır
INTENT_FALLBACK = [
    "Eksik ürün","Şifre sıfırlama","İade","Kupon","İptal","Stok","Ödeme","Kargo",
    "Hasarlı ürün","Değişim","Ürün","İndirim","Hesap bilgisi","Hesap kapatma",
    "Abonelik","Web sitesi","Yorum","Teknik sorun","Sipariş","Beden","Adres hatası"
]

# ---------- yardımcı: zaman alanları ----------
def _safe_parse_dt(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    # yaygın formatları dene
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%d.%m.%Y %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # ISO auto parse
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _add_time_cols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Veri setinde zaman alanları varsa parse eder ve standart kolonları ekler:
    - sohbet_baslangic, sohbet_bitis (string)
    - toplam_sure_saniye (int)
    Eğer veri setinde zaman alanı yoksa kolonlar None/NaN olarak eklenir (yönerge uyumu için).
    """
    df = df.copy()

    # Veri kaynaklarına göre muhtemel kolon isimleri
    start_candidates = ["sohbet_baslangic","start_ts","conversation_start","baslangic","start_time"]
    end_candidates   = ["sohbet_bitis","end_ts","conversation_end","bitis","bitiş","end_time"]

    start_col = next((c for c in start_candidates if c in df.columns), None)
    end_col   = next((c for c in end_candidates if c in df.columns), None)

    if start_col:
        df["__start_dt"] = df[start_col].map(_safe_parse_dt)
    else:
        df["__start_dt"] = None

    if end_col:
        df["__end_dt"] = df[end_col].map(_safe_parse_dt)
    else:
        df["__end_dt"] = None

    # süre
    def _dur_seconds(row):
        a, b = row["__start_dt"], row["__end_dt"]
        if a and b:
            try:
                return int((b - a).total_seconds())
            except Exception:
                return None
        return None

    df["toplam_sure_saniye"] = df.apply(_dur_seconds, axis=1)

    def _fmt(x):
        try:
            return x.strftime("%Y-%m-%d %H:%M") if x else None
        except Exception:
            return None

    df["sohbet_baslangic"] = df["__start_dt"].map(_fmt)
    df["sohbet_bitis"]     = df["__end_dt"].map(_fmt)

    return df.drop(columns=["__start_dt","__end_dt"], errors="ignore")

# ---------- JSON okuma ----------
def _load_json_any(path: Path) -> List[Dict[str, Any]]:
    """
    Tek JSON (liste) ya da JSONL (her satır bir JSON) dosyasını okur.
    """
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return []
    # JSON array
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    # JSONL
    recs: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                recs.append(obj)
        except Exception:
            # boş/bozuk satırı atla
            continue
    return recs

# ---------- konuşma metni toparlama ----------
def _coalesce_dialog(rec: Dict[str, Any]) -> str:
    """
    'dialog_text' alanı rekte yoksa, 'messages' gibi yapıdan birleştir.
    Basit birleştirme: "[Müşteri]: ...\n[Bot]: ...\n" biçiminde.
    """
    if "dialog_text" in rec and rec["dialog_text"]:
        return str(rec["dialog_text"])

    msgs = rec.get("messages") or rec.get("dialog") or rec.get("turns") or []
    out_lines: List[str] = []
    for m in msgs:
        role = str(m.get("role") or m.get("speaker") or "").strip().lower()
        text = str(m.get("text") or m.get("content") or "").strip()
        if not text:
            continue
        if role in ["user","customer","musteri","müşteri"]:
            tag = "[Müşteri]"
        elif role in ["assistant","bot","agent","mila"]:
            tag = "[Bot]"
        else:
            tag = "[Konuşmacı]"
        out_lines.append(f"{tag} {text}")
    return "\n".join(out_lines).strip()

# ---------- public API ----------
def load_conversations(in_json: str) -> pd.DataFrame:
    """
    JSON/JSONL dosyadan temel kolonları üretir:
      - conversation_id
      - dialog_text
      - gold_sentiment, gold_intent, gold_yanit_durumu, gold_tur, (opsiyonel) gold_intent_detay
    + yönerge gereği zaman kolonları:
      - sohbet_baslangic, sohbet_bitis, toplam_sure_saniye
    """
    path = Path(in_json)
    if not path.exists():
        raise SystemExit(f"[ERR] Veri dosyası bulunamadı: {path.resolve()}")

    records = _load_json_any(path)
    rows: List[Dict[str, Any]] = []
    for i, rec in enumerate(records):
        rid = rec.get("conversation_id") or rec.get("id") or rec.get("cid") or i
        dialog_text = _coalesce_dialog(rec)

        row = {
            "conversation_id": rid,
            "dialog_text": dialog_text,
            # gold alanları varsa çek
            "gold_sentiment": rec.get("gold_sentiment"),
            "gold_intent": rec.get("gold_intent"),
            "gold_yanit_durumu": rec.get("gold_yanit_durumu"),
            "gold_tur": rec.get("gold_tur"),
            "gold_intent_detay": rec.get("gold_intent_detay"),
            # olası zaman alanlarını geçici taşı (parse için)
            "sohbet_baslangic": rec.get("sohbet_baslangic") or rec.get("start_ts") or rec.get("conversation_start"),
            "sohbet_bitis": rec.get("sohbet_bitis") or rec.get("end_ts") or rec.get("conversation_end"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Zaman sütunları ekle/parse et
    df = _add_time_cols(df)

    # Kolon sırasını okunur kıl
    prefer = [
        "conversation_id", "dialog_text",
        "sohbet_baslangic", "sohbet_bitis", "toplam_sure_saniye",
        "gold_sentiment", "gold_intent", "gold_yanit_durumu", "gold_tur", "gold_intent_detay",
    ]
    rest = [c for c in df.columns if c not in prefer]
    df = df[prefer + rest]
    return df

def build_allowed_intents(df: pd.DataFrame) -> List[str]:
    """
    Gold intent kolonundan izinli listeyi çıkarır; yoksa fallback sabit listeyi döner.
    """
    if "gold_intent" in df.columns:
        vals = sorted([v for v in df["gold_intent"].dropna().astype(str).unique().tolist() if v.strip()])
        if vals:
            return vals
    return INTENT_FALLBACK[:]
