<!-- ====== HERO BANNER ====== -->
<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=0:7F00FF,100:E100FF&height=120&section=header&text=Mila%20AI%20Eval&fontSize=52&fontColor=ffffff&fontAlignY=35" alt="Mila AI Eval Banner">
</p>

<p align="center">
  <a href="#"><img src="https://readme-typing-svg.demolab.com?font=Inter&size=26&pause=800&color=FFFFFF&center=true&vCenter=true&repeat=false&width=900&lines=E-ticaret+sohbetlerini+anlam+temelli+etiketleyen%2C+%C3%B6l%C3%A7en+ve+raporlayan+pipeline" alt="typing banner"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="python">
  <img src="https://img.shields.io/badge/OpenAI-Structured%20Output-000000?logo=openai&logoColor=white" alt="openai">
  <img src="https://img.shields.io/badge/Pandas-Data%20Frame-150458?logo=pandas&logoColor=white" alt="pandas">
  <img src="https://img.shields.io/badge/ReportLab-PDF%20Reports-FF6C37" alt="reportlab">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="license">
</p>

---

<h1 align="center">🧠 Mila AI Eval — Anlam Temelli Değerlendirme Pipeline’ı</h1>

E-ticaret müşteri destek sohbetlerini **anlam temelli** (semantic) etiketleyen, sonuçları **ölçen** ve **raporlayan** uçtan uca sistem.

- ✅ **Structured Output (Pydantic)** → her diyalog için **geçerli, tek satır JSON**
- 📊 **Değerlendirme metrikleri** → Accuracy & Macro-F1 + “Üçü birden doğru”
- 🧾 **Raporlama** → 5 PDF (Doğruluk Özeti, SWOT, Geliştirme Önerileri, Müşteri Talepleri Özeti, Teknik Notlar)
- 📦 **Teslim paketi** → `deliverables/` klasörünü tek komutla zip
- 🇹🇷 **Türkçe glif uyumu** → ReportLab + Windows’ta **Arial** fallback

---

## 🧭 İçindekiler
- [Mimari Genel Bakış](#-mimari-genel-bakış)
- [Klasör Yapısı](#-klasör-yapısı)
- [Kurulum](#-kurulum)
- [.env ve Yapılandırma](#-env-ve-yapılandırma)
- [Hızlı Başlangıç](#-hızlı-başlangıç)
- [Girdi Formatı](#-girdi-formatı)
- [Üretilen Çıktılar](#-üretilen-çıktılar)
- [Raporlar](#-raporlar)
- [EDA (Opsiyonel)](#-eda-opsiyonel)
- [Model ve Structured Output](#-model-ve-structured-output)
- [Troubleshooting](#-troubleshooting)
- [Lisans ve Güvenlik](#-lisans-ve-güvenlik)
- [Katkı](#-katkı)

---

## 🧩 Mimari Genel Bakış
1. **İnferans** (`src/llm_infer.py`)  
   Pydantic şeması ile structured parse → **geçerli JSON zorunlu**. Boş/uygunsuz yanıt → **fail-fast** (koşu durur).
2. **Değerlendirme** (`src/metrics_eval.py`)  
   Accuracy & Macro-F1 (5 alan) + “Üçü birden doğru”, confusion CSV’leri.
3. **Raporlama & Paketleme** (`src/generate_reports.py`, `src/package_deliverables.py`)  
   5 PDF rapor + teslim paketi zip.

---

## 🗂️ Klasör Yapısı
mila-ai-eval/
├─ src/
│ ├─ eval_pipeline.py # Uçtan uca değerlendirme
│ ├─ data_load.py # Veri yükleme + zaman kolonları
│ ├─ llm_infer.py # LLM (Pydantic structured output)
│ ├─ metrics_eval.py # Excel + confusion CSV
│ ├─ generate_reports.py # 5 PDF rapor
│ └─ package_deliverables.py # deliverables/ → zip
├─ data/raw/ # Girdi JSON/JSONL
├─ outputs/ # predictions/ + eval/ (Excel & confusion)
├─ deliverables/ # PDF’ler (+ opsiyonel Excel/CSV)
├─ notebooks/ # EDA (opsiyonel)
├─ src/prompt_template.txt
├─ .gitignore
└─ README.md

> `.gitignore` içinde `.env`, `.venv/`, `outputs/`, `deliverables/`, büyük dosyalar & fontlar saklanır.

---

## ⚙️ Kurulum
```bash
# Python 3.10+ önerilir
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
🔐 .env ve Yapılandırma

Kök dizine .env (repo’ya ekleme):

OPENAI_API_KEY=sk-...         # zorunlu
OPENAI_BASE_URL=              # opsiyonel (proxy/self-host)
OPENAI_MODEL=gpt-5-nano       # opsiyonel; CLI ile de geçirilebilir
⏱️ Hızlı Başlangıç

1) Değerlendirme (LLM tahmin + Excel + confusion)

Windows (CMD):

python src\eval_pipeline.py ^
  --in-json data\raw\20-sohbet-trendyol-mila.json ^
  --prompt src\prompt_template.txt ^
  --pred-out outputs\predictions\preds_mila.csv ^
  --excel-out outputs\eval\mila_eval.xlsx ^
  --cm-dir outputs\eval\confusions ^
  --model gpt-5-nano


macOS/Linux/PowerShell:

python src/eval_pipeline.py --in-json data/raw/20-sohbet-trendyol-mila.json \
  --prompt src/prompt_template.txt \
  --pred-out outputs/predictions/preds_mila.csv \
  --excel-out outputs/eval/mila_eval.xlsx \
  --cm-dir outputs/eval/confusions \
  --model gpt-5-nano


2) PDF Raporları Üret

python src/generate_reports.py \
  --xlsx outputs/eval/mila_eval.xlsx \
  --preds outputs/predictions/preds_mila.csv \
  --outdir deliverables \
  --project "Trendyol Mila Sohbet Botu" \
  --model gpt-5-nano \
  --prepared_by "Aslı Aktaş"


3) Teslim Paketini Zip’le

python src/package_deliverables.py --dir deliverables --out mila-deliverables

🧵 Girdi Formatı

JSON/JSONL desteklenir. Önerilen alanlar:

conversation_id (yoksa indeks kullanılır)

dialog_text — yoksa messages/turns’tan otomatik derlenir

gold_* — (opsiyonel) gold_sentiment, gold_intent, gold_yanit_durumu, gold_tur, gold_intent_detay

Zaman alanları (opsiyonel): sohbet_baslangic, sohbet_bitis (veya start_ts, end_ts)
→ Excel/data sayfasında sohbet_baslangic, sohbet_bitis, toplam_sure_saniye

Örnek alternatif şema:

{
  "conversation_id": "abc-123",
  "messages": [
    {"role": "user", "text": "Kargom nerede?"},
    {"role": "assistant", "text": "Takip linki ..."}
  ]
}

📤 Üretilen Çıktılar

outputs/predictions/preds_mila.csv — tek satır etiket + prompt & raw JSON

outputs/eval/mila_eval.xlsx — data (gold+pred+zaman) & metrics

outputs/eval/confusions/ — confusion CSV’leri (5 alan)

deliverables/ — 5 PDF:
01_dogruluk_ozet.pdf, 02_SWOT.pdf, 03_gelistirme_onerileri.pdf,
04_musteri_talepleri_ozeti.pdf, 05_teknik_notlar.pdf

mila-deliverables.zip — teslim paketi

🧾 Raporlar

01 Doğruluk Özeti → Accuracy & Macro-F1 + “Üçü birden doğru”, kısa içgörüler

02 SWOT → Güçlü/Zayıf/Fırsat/Tehdit

03 Geliştirme Önerileri → Hızlı kazanımlar (özellikle tür için hafif post-fix)

04 Müşteri Talepleri Özeti → Top intent’ler, örnek alıntılar, intent_detay dağılımı

05 Teknik Notlar → Komutlar, klasör yapısı, kalite güvencesi

📈 EDA (Opsiyonel)

Notebooks klasöründe hızlı EDA defteri:

Dağılım kıyası: Sentiment / Yanıt durumu / Tür / Intent (Top-10)

Intent Confusion (Top-10) ısı haritası

Özet skorlar: Accuracy & Macro-F1 bar grafiği

🧠 Model ve Structured Output

Varsayılan: gpt-5-nano (temperature yok)

Alternatif: gpt-4o-mini, gpt-4.1-mini

Akış:

chat.completions.parse(...) → Pydantic nesnesi

Olmazsa response_format={"type":"json_object"} fallback

Pydantic doğrulaması (kapalı kümeler)

Boş/uygunsuz yanıt → fail-fast (koşu durur)

🧰 Troubleshooting

PDF’de Türkçe karakter bozuk → Windows’ta Arial fallback; DejaVu için font dosyalarını assets/fonts/ altına ekle.

reportlab bulunamadı → pip install reportlab

Repository not found (push) → GitHub’da repo’yu oluştur →
git remote set-url origin https://github.com/<user>/mila-ai-eval.git && git push -u origin main

Boş/parse edilemeyen LLM yanıtı → .env ve model adını kontrol et; structured parse bilerek koşuyu durdurur.

🛡️ Lisans ve Güvenlik

Lisans: MIT (önerilir).

Kişisel veri içeren sohbetler anonimleştirilmelidir (KVKK/GDPR).

.env, .venv/, outputs/, deliverables/ ve büyük dosyalar .gitignore kapsamındadır.

<h2 align="center">🤝 Katkı</h2> <p align="center"> Issues ve PR’lara açığız. <br/> <strong>Hazırlayan:</strong> Aslı Aktaş — İyileştirme önerilerinizi bekliyoruz! ✨ </p> ```
