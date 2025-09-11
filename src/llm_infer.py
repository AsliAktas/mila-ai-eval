# -*- coding: utf-8 -*-
"""
LLM inference katmanı (structured output)
-----------------------------------------
- Amaç: Tek sohbet → tek satır etiket üretmek.
- Yöntem: Pydantic şeması ile "structured output" (parse) kullanılır.
  * Önce .parse ile Pydantic nesnesi istenir.
  * Başarısız olursa json_object fallback ve Pydantic doğrulama.
- Güvenlik: Boş/uygunsuz yanıt gelirse üst katmana RuntimeError/SystemExit fırlatılır
  (kullanıcı isteğine uygun: "boşsa durdur").

Kullanım:
- predict_conversations(...) dış API’dir; CSV’ye yazar.
- .env: OPENAI_API_KEY (+ opsiyonel OPENAI_BASE_URL, OPENAI_MODEL)
"""
from __future__ import annotations

import os, json, re
from pathlib import Path
from typing import Dict, List, Literal, Optional
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, field_validator

# ------------ Sabit Sözlükler (kapalı kümeler) ------------
SENT_ALLOWED = ["Pozitif", "Negatif", "Nötr"]
ANS_ALLOWED  = ["Çözüldü", "Çözülemedi"]
TUR_ALLOWED  = ["Şikayet", "Sorun", "Bilgi alma", "İstek", "Soru", "İade"]

INTENT_ALLOWED = [
    "Eksik ürün","Şifre sıfırlama","İade","Kupon","İptal","Stok","Ödeme","Kargo",
    "Hasarlı ürün","Değişim","Ürün","İndirim","Hesap bilgisi","Hesap kapatma",
    "Abonelik","Web sitesi","Yorum","Teknik sorun","Sipariş","Beden","Adres hatası"
]

INTENT_DETAY_ALLOWED = [
    "Sipariş teslimatında eksik ürün","E-posta linki gelmemesi","İade prosedürü hakkında bilgi",
    "Kupon kodunun çalışmaması","Sipariş iptali","İade kargosu takibi","Değişim/iade yapılamaması",
    "Üyelik bilgisi güncelleme","Fatura fiyatı hatası","Sipariş iptali yapılamaması",
    "Stok yenileme tarihi","Çifte çekim","Kargo durumu","Kredi kartı reddedilmesi",
    "Ürün beden tablosu","Yanlış adres girişi","Yorum yayınlanmaması","Teknik hata",
    "Hesaptan para çekilip siparişin oluşmaması","Ürün bilgisi","Eksik promosyon ürünleri",
    "Para iadesi gecikmesi","Kargodan kaynaklı hasar","Değişim seçeneği olmaması",
    "Kampanya bilgisi","Yanlış ürün gönderimi","Hesap kapatma",
    "Stokta görünen ürünün eksik gelmesi","İade kodunun geçersiz olması",
    "Yanlış teslimat adresi","Sipariş durumu","Ödemenin tamamlanmaması",
    "Beden uyuşmazlığı","Kargonun gecikmesi","Garanti kapsamında tamir",
    "E-posta aboneliği iptali","Kargo gecikmesi","İade süreci gecikmesi"
]

# ------------ Pydantic Yapısal Şema ------------
SentimentLit      = Literal["Pozitif","Negatif","Nötr"]
AnswerLit         = Literal["Çözüldü","Çözülemedi"]
TurLit            = Literal["Şikayet","Sorun","Bilgi alma","İstek","Soru","İade"]
IntentLit         = Literal[tuple(INTENT_ALLOWED)]
IntentDetayLit    = Literal[tuple(INTENT_DETAY_ALLOWED)]

class ConversationLabel(BaseModel):
    # Çıktı şeması: her alan kapalı kümeyle kısıtlı
    yanit_durumu: AnswerLit
    sentiment: SentimentLit
    tur: TurLit
    intent: IntentLit
    intent_detay: IntentDetayLit

    # Ek güvenlik: trimming
    @field_validator("*", mode="before")
    @classmethod
    def _trim(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

# ------------ Yardımcılar ------------
SYSTEM_SEMANTIC = (
    "Türkçe e-ticaret müşteri sohbetlerini yalnızca anlam/niyet temelinde etiketleyen titiz bir sınıflandırıcısın. "
    "Çıktın SADECE tek bir yapılandırılmış nesne olacak; düşünme adımlarını yazmayacaksın."
)

def robust_json_line(s: str) -> Dict:
    """Serbest metin içinden ilk JSON nesnesini ayıklar; yoksa {} döner."""
    if not s:
        return {}
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        try:
            return json.loads(m.group(0).replace("'", '"'))
        except Exception:
            return {}

# ------------ LLM Çağrısı: Structured Output → .parse ------------
def call_llm_structured(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> ConversationLabel:
    """
    Öncelik: structured parse (pydantic). SDK/endpoint desteklemiyorsa json_object → manuel parse fallback.
    Boş/uygunsuz yanıtta RuntimeError fırlatır (koşuyu durdurmak için üst katmanda yakalanır).
    """
    # 1) Pydantic parse (chat.completions.parse)
    try:
        comp = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=ConversationLabel,
        )
        parsed: Optional[ConversationLabel] = comp.choices[0].message.parsed  # type: ignore
        if parsed is None:
            raise RuntimeError("LLM parsed object is None")
        return parsed
    except Exception:
        # 2) JSON object fallback (çoğu model destekler)
        try:
            comp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt + "\n\nSADECE tek satır JSON yaz."}
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=180,
            )
            raw = (comp.choices[0].message.content or "").strip()
            js = robust_json_line(raw)
            if not js:
                raise RuntimeError("LLM returned empty/invalid JSON in json_object mode")
            # Pydantic doğrulamasından geçir
            return ConversationLabel(**js)
        except Exception as e2:
            raise RuntimeError(f"Structured output başarısız: {e2}")

# ------------ Ana Çalışan: predict_conversations ------------
def predict_conversations(
    df_convs: pd.DataFrame,
    prompt_template_path: str,
    intents: List[str],
    out_path: str,
    model_override: Optional[str] = None,
):
    """
    Structured output (parse) ile tek geçiş tahmin üretir.
    Boş/uygunsuz yanıt durumunda SystemExit ile koşuyu durdurur.
    """
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = (os.getenv("OPENAI_BASE_URL") or "").strip().strip('\'"')
    model = model_override or os.getenv("OPENAI_MODEL", "gpt-5-nano")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY bulunamadı (.env).")
    client = OpenAI(api_key=api_key, base_url=base_url or None)

    # Prompt şablonu
    prompt_tmpl = Path(prompt_template_path).read_text(encoding="utf-8")
    if "<<DIALOG_BLOK>>" not in prompt_tmpl:
        raise SystemExit("Prompt template içinde <<DIALOG_BLOK>> bulunamadı.")

    preds = []
    empty_count = 0

    for _, row in df_convs.iterrows():
        cid = row["conversation_id"]
        dialog = str(row["dialog_text"] or "").strip()
        # Şablona enjekte
        prompt = prompt_tmpl.replace("<<DIALOG_BLOK>>", dialog)
        prompt_used = (prompt[:800] + "…") if len(prompt) > 800 else prompt

        # LLM structured parse
        try:
            parsed = call_llm_structured(client, model, SYSTEM_SEMANTIC, prompt)
            js = parsed.model_dump()
        except Exception as e:
            # Boş/uygunsuz → koşuyu durdur (kullanıcı isteği: "boşsa durdur")
            empty_count += 1
            raise SystemExit(f"LLM structured yanıt hatası/boş çıktı. conversation_id={cid} | model={model} | detay={e}")

        # Kayıt (CSV satırı)
        preds.append({
            "conversation_id": cid,
            "pred_yanit_durumu": js["yanit_durumu"],
            "pred_sentiment":    js["sentiment"],
            "pred_tur":          js["tur"],
            "pred_intent":       js["intent"],
            "pred_intent_detay": js["intent_detay"],
            "prompt_used":       prompt_used,
            "raw_model_output":  json.dumps({"final": js}, ensure_ascii=False),
        })

    # Çıktı CSV
    out = pd.DataFrame(preds)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False, encoding="utf-8")
    print(f"[OK] Tahminler kaydedildi: {out_path} | model={model}")
