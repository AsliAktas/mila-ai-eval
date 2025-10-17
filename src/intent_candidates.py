# -*- coding: utf-8 -*-
"""
Heuristik intent aday bulucu
----------------------------
- Tüm diyaloğu ve son kullanıcı dönüşlerini (2x ağırlık) anahtar kelimelerle tarar.
- Sadece verilen `allowed` listesinden etiket döndürür (skora göre sıralı).
- Hiç eşleşme yoksa `allowed[:top_k]` fallback'i kullanılır.
- "İade" sapmasını azaltmak için iade ipuçları yoksa "İade" adayı elenir.
"""

import re
from collections import Counter
from typing import List

# Anahtar kelime sözlüğü (basit, domain-özel örnekler)
INTENT_KEYWORDS = {
    "İade": ["iade", "para iadesi", "ücret iadesi", "refund", "return", "iade kodu", "iade etiketi", "geri göndermek"],
    "İptal": ["iptal", "gönderimi durdur", "iptal etmek"],
    "Kargo": ["kargo", "kurye", "teslimat", "dağıtım", "gecikme", "takip", "nerede", "ne zaman"],
    "Ödeme": ["ödeme", "kart", "provizyon", "para çekildi", "çekim", "çifte çekim", "red", "kredi kartı", "banka"],
    "Kupon": ["kupon", "indirim kodu", "promosyon kodu", "kampanya", "minimum sepet"],
    "Adres hatası": ["yanlış adres", "adresimi", "adres değişikliği", "adres düzelt", "adres güncelle"],
    "Eksik ürün": ["eksik", "parça yok", "çıkmadı", "hediye yok", "promosyon çıkmadı"],
    "Hasarlı ürün": ["kırık", "hasarlı", "çatlak", "ezik", "bozuk"],
    "Beden": ["beden", "ölçü", "büyük geldi", "küçük geldi", "beden tablosu"],
    "Değişim": ["değişim", "değiştirmek"],
    "Stok": ["stok", "yenilenecek", "tükendi"],
    "Sipariş": ["sipariş", "sipariş no", "sipariş durumu"],
    "Hesap bilgisi": ["hesap", "üye bilgisi", "profil", "mail adresi", "telefon"],
    "Hesap kapatma": ["hesap kapat", "üyeliği sil"],
    "Şifre sıfırlama": ["şifre", "parola", "giremiyorum", "mail gelmedi", "sıfırla", "link"],
    "Ürün": ["ürün bilgisi", "özellik", "model", "uyum"],
    "İndirim": ["indirim", "kampanya"],
    "Web sitesi": ["site", "uygulama", "hata", "çöküyor"],
    "Yorum": ["yorum", "değerlendirme"],
    "Teknik sorun": ["hata", "bug", "teknik"],
}
IADE_CUES = ["iade", "para iadesi", "ücret iadesi", "refund", "return", "iade kodu", "iade etiketi", "geri göndermek"]

def _score_for(label: str, text: str) -> int:
    """Basit anahtar kelime sayımı (tam kelime) ile skor üretir."""
    keys = INTENT_KEYWORDS.get(label, [])
    s = 0
    for k in keys:
        s += len(re.findall(r"\b"+re.escape(k)+r"\b", text))
    return s

def find_candidates(dialog_text: str, allowed: List[str], top_k: int = 5) -> List[str]:
    """
    allowed içinden en yüksek skorlu top_k etiketi döndür.
    - Son 6 satırdaki kullanıcı mesajlarına 2x ağırlık.
    - İade ipucu yoksa "İade" adayını listeden çıkar.
    """
    if not dialog_text:
        return allowed[:top_k]
    lower = dialog_text.lower()

    # Son kullanıcı bloklarını yakala (örn. "[müşteri]" veya "müşteri:" içeren satırlar)
    blocks = [b.strip() for b in lower.split("\n") if b.strip()]
    last_user = " ".join([b for b in blocks[-6:] if b.startswith("[müşteri]") or b.startswith("[u]") or "müşteri:" in b or "kullanıcı:" in b])

    base = Counter()
    for label in allowed:
        s_all  = _score_for(label, lower)
        s_last = _score_for(label, last_user) * 2  # recency: son kullanıcı sözlerine 2x
        score = s_all + s_last
        if score != 0:
            base[label] = score

    # “İade mıknatısı” etkisini kırmak: iade ipucu yoksa İade’yı çıkar
    has_iade_cue = any(k in lower for k in IADE_CUES) or any(k in last_user for k in IADE_CUES)
    if "İade" in base and not has_iade_cue:
        base.pop("İade", None)

    if base:
        return [lab for lab, _ in base.most_common(top_k)]
    return allowed[:top_k]
