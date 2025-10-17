# -*- coding: utf-8 -*-
"""
LLM çıkarım katmanı (yapılandırılmış çıktı)
-----------------------------------------
- Amaç: Tek bir sohbetten tek satırlık etiketler üretmek.
- Yöntem: Pydantic şeması ile "yapılandırılmış çıktı" (structured output) kullanılır.
  * İlk olarak, çıktıyı doğrudan Pydantic nesnesine dönüştürmeye çalışır.
  * Başarısız olursa, bir JSON nesnesi çıkarmaya geri döner ve ardından Pydantic ile doğrular.
- Güvenlik: Kullanıcı isteğine uygun olarak, eğer yanıt boş veya uygunsuz gelirse, süreci durdurmak için bir RuntimeError/SystemExit hatası fırlatır ("boşsa durdur" kuralına göre).

Kullanım:
- `predict_conversations` işlevi ana harici API'dir; çıktıyı bir CSV dosyasına yazar.
- `.env` dosyası `OPENAI_API_KEY` veya `GROQ_API_KEY` içermelidir.

YENİ eklemeler (yapıyı bozmadan entegre edildi):
- XLSX'ten okumak için yardımcı işlevler.
- Komut satırı arayüzü (CLI): `--in-xlsx` argümanı dosyadan okur ve `predict_conversations` işlevini çağırır.
"""
from __future__ import annotations

import os, json, re, sys, argparse
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

# API istemcilerini koşullu olarak içe aktar
try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# İsteğe bağlı ilerleme çubuğu
try:
    from tqdm import tqdm as _tqdm
except ImportError:
    _tqdm = None  # tqdm yüklü değilse sessizce devam eder


# ------------ Sabit Sözlükler (kapalı kümeler) ------------
SENT_ALLOWED = ["Pozitif", "Negatif", "Nötr"]
ANS_ALLOWED = ["Çözüldü", "Çözülemedi"]
TUR_ALLOWED = ["Şikayet", "Sorun", "Bilgi alma", "İstek", "Soru", "İade"]


# ------------ Pydantic Şeması ------------
class IntentSchema(BaseModel):
    """
    LLM çıktısı için yapıyı ve doğrulamayı tanımlar.
    """
    yanit_durumu: Literal["Çözüldü", "Çözülemedi"]
    sentiment: Literal["Pozitif", "Negatif", "Nötr"]
    tur: Literal["Şikayet", "Sorun", "Bilgi alma", "İstek", "Soru", "İade"]
    intent: str
    intent_detay: str

    @field_validator("yanit_durumu")
    @classmethod
    def check_yanit_durumu(cls, v):
        if v not in ANS_ALLOWED:
            raise ValueError(f"Geçersiz 'yanit_durumu': {v}. Şu değerlerden biri olmalıdır: {ANS_ALLOWED}")
        return v

    @field_validator("sentiment")
    @classmethod
    def check_sentiment(cls, v):
        if v not in SENT_ALLOWED:
            raise ValueError(f"Geçersiz 'sentiment': {v}. Şu değerlerden biri olmalıdır: {SENT_ALLOWED}")
        return v
    
    @field_validator("tur")
    @classmethod
    def check_tur(cls, v):
        if v not in TUR_ALLOWED:
            raise ValueError(f"Geçersiz 'tur': {v}. Şu değerlerden biri olmalıdır: {TUR_ALLOWED}")
        return v


# ------------ Yardımcı Fonksiyonlar ------------
def _extract_json(text: str) -> Optional[Dict]:
    """
    Verilen metinden bir JSON nesnesi çıkarır (eğer varsa).
    """
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    
    json_str = match.group(0)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None

def read_conversations_from_xlsx(
    xlsx_path: str,
    id_col: str = "sohbet_id",
    text_col: str = "tam_sohbet",
    sheet_name: str = "sohbetler",
) -> pd.DataFrame:
    """
    Bir XLSX dosyasından sohbetleri okur ve DataFrame'e dönüştürür.
    """
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
    df = df.rename(columns={id_col: "conversation_id", text_col: "dialog_text"})
    return df[["conversation_id", "dialog_text"]]


def _call_llm_with_retries(
    client,
    prompt: str,
    intents: Optional[List[str]] = None,
    max_retries: int = 2,
    model: Optional[str] = None,
) -> Dict:
    """
    LLM'i çağırır ve yanıtı doğrulamaya çalışır.
    """
    if not prompt:
        return {"error": "Boş prompt", "raw_model_output": ""}

    if not model:
        raise SystemExit("Hata: '--model' argümanı belirtilmedi.")

    # Sistem mesajına intent listesi ekleniyor
    system_prompt = (
        f"Verilen sohbeti aşağıdaki formatta sınıflandır: "
        f"{IntentSchema.model_json_schema()}"
    )
    if intents:
        system_prompt += f"\nSadece bu intent'leri kullan: {intents}"

    for attempt in range(max_retries):
        try:
            # İstemci türüne göre API çağrısını yap
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            
            model_output = response.choices[0].message.content
            
            # Pydantic ile doğrulama
            validated_output = IntentSchema.model_validate_json(model_output)
            return validated_output.model_dump_json()

        except Exception as e:
            # Hata durumunda yeniden dene
            print(f"Hata oluştu (deneme {attempt+1}/{max_retries}): {e}", file=sys.stderr)
            if attempt == max_retries - 1:
                return {"error": f"Maksimum deneme sayısı aşıldı: {e}", "raw_model_output": model_output if 'model_output' in locals() else ""}
    
    return {"error": "Tahmin yapılamadı.", "raw_model_output": ""}

def predict_conversations(
    conversations: pd.DataFrame,
    prompt_template: str,
    out_path: str,
    intents: Optional[List[str]] = None,
    model: Optional[str] = None,
) -> pd.DataFrame:
    """
    Sohbetleri tahmin eder ve CSV'ye yazar.
    :param conversations: 'conversation_id' ve 'dialog_text' sütunlarını içeren DataFrame.
    :param prompt_template: `<<DIALOG_BLOK>>` içeren prompt şablonu.
    :param out_path: Çıktı CSV dosya yolu.
    :param intents: İsteğe bağlı intent listesi (kapalı küme).
    :param model: Kullanılacak modelin adı.
    :return: Tahminleri içeren bir DataFrame.
    """
    if not _tqdm:
        print("Uyarı: tqdm kütüphanesi yüklü değil, ilerleme çubuğu gösterilmeyecek.")

    # API istemcisini başlat
    load_dotenv()
    
    client = None
    if model and 'gpt' in model.lower():
        if OpenAI:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        else:
            raise SystemExit("Hata: OpenAI kütüphanesi yüklü değil. Lütfen `pip install openai` komutunu çalıştırın.")
    elif model:
        if Groq:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        else:
            raise SystemExit("Hata: Groq kütüphanesi yüklü değil. Lütfen `pip install groq` komutunu çalıştırın.")
    
    if not client:
        raise SystemExit("Hata: '--model' argümanı veya .env içinde API anahtarı tanımlı değil.")
        
    predictions = []
    
    iter_convs = _tqdm(conversations.itertuples(), total=len(conversations)) if _tqdm else conversations.itertuples()
    
    for row in iter_convs:
        full_prompt = prompt_template.replace("<<DIALOG_BLOK>>", row.dialog_text)
        
        llm_response = _call_llm_with_retries(
            client,
            full_prompt,
            intents=intents,
            model=model,
        )
        
        predictions.append({
            "conversation_id": row.conversation_id,
            "prediction": llm_response
        })

    df_preds = pd.DataFrame(predictions)
    
    df_preds.to_csv(out_path, index=False)

    return df_preds

# ------------ CLI Giriş Noktası ------------
def _parse_args() -> argparse.Namespace:
    """
    CLI argümanlarını ayrıştırır.
    """
    ap = argparse.ArgumentParser(description="LLM Çıkarım CLI.")
    ap.add_argument("--in-xlsx", type=str, required=False,
                    help="Girdi XLSX yolu (CLI için zorunlu)")
    ap.add_argument("--sheet-name", type=str, required=False, default="sohbetler",
                    help="XLSX içindeki sayfa adı")
    ap.add_argument("--id-col", type=str, required=False, default="sohbet_id",
                    help="Sohbet ID sütunu adı")
    ap.add_argument("--text-col", type=str, required=False, default="tam_sohbet",
                    help="Sohbet metin sütunu adı")
    ap.add_argument("--prompt", type=str, required=False, default="src/prompt_template.txt",
                    help="<<DIALOG_BLOK>> içeren prompt şablon dosyası")
    ap.add_argument("--out", type=str, required=False, default="outputs/preds.csv",
                    help="Çıktı CSV yolu")
    ap.add_argument("--model", type=str, required=False, default=None,
                    help="Modeli geçersiz kılma (örn: gpt-3.5-turbo).")
    ap.add_argument("--intents", type=str, nargs="*", default=None,
                    help="İsteğe bağlı intent listesi (kullanılmıyorsa boş bırak)")

    return ap.parse_args()


def main() -> None:
    """
    CLI'yı çalıştırmak için ana işlev.
    """
    args = _parse_args()

    if not args.in_xlsx:
        print("Uyarı: --in-xlsx verilmedi. Bu dosya normalde dışarıdan DataFrame alarak da çalışır (predict_conversations). CLI ile XLSX kullanmak için --in-xlsx verin.", file=sys.stderr)
        sys.exit(2)

    df_convs = read_conversations_from_xlsx(
        xlsx_path=args.in_xlsx,
        id_col=args.id_col,
        text_col=args.text_col,
        sheet_name=args.sheet_name,
    )

    intents = args.intents if args.intents else []

    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        raise SystemExit(f"Hata: Prompt şablon dosyası bulunamadı: {prompt_path}")
    prompt_template = prompt_path.read_text(encoding="utf-8")

    predict_conversations(
        conversations=df_convs,
        prompt_template=prompt_template,
        out_path=args.out,
        intents=intents,
        model=args.model,
    )

    print(f"\nTahminler başarıyla {args.out} dosyasına yazıldı.")


if __name__ == "__main__":
    main()