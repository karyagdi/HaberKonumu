import re
import unicodedata


DEFAULT_NOISE_PHRASES = {
    "yazdır",
    "muhabir",
    "haber merkezi",
    "mahreç",
    "topluluk kuralları",
    "yorumunuz",
    "yorumlar",
    "giriş yap",
    "sosyal sayfalar",
    "galeri",
    "anket",
    "koga a.ş.",
    "medya grubu",
    "veri politikası",
    "kullanım şartları",
    "tüm hakları saklıdır",
    "reklam seçeneklerimizi inceleyin",
    "oturum açın",
    "buraya tıklayın",
    "yorumunuz için teşekkürler",
    "kırmızı alanlar eksik",
    "haber ajansları tarafından servis edilen",
    "sitemize ajanslar üzerinden aktarılan",
    "gösterim gerçekleşti",
    "resmi ilanlar",
    "takip et",
}


def normalize_text_for_dedup(text):
    text = text or ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_extracted_text(text):
    text = text or ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ")
    text = text.replace("\r", " ").replace("\t", " ")
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \n-–|:;,")


def is_metadata_line(text):
    text = clean_extracted_text(text)

    if not text:
        return True

    lower_text = text.lower()

    if re.search(r"\b\d{1,2}\s+[a-zçğıöşü]{3,10}\s+\d{4}\b", lower_text) and (
        "gündem" in lower_text
        or "asayiş" in lower_text
        or "okunma" in lower_text
        or "yazdır" in lower_text
    ):
        return True

    if lower_text.startswith("#"):
        return True

    if re.search(r"\b(?:tel|telefon|whatsapp)\s*[:\-]?\s*\d", lower_text):
        return True

    if re.search(r"©|\bcopyright\b", lower_text):
        return True

    return False


def is_noise_text(text, noise_phrases=None):
    text = clean_extracted_text(text)
    if not text:
        return True

    lower_text = text.lower()
    phrases = noise_phrases or DEFAULT_NOISE_PHRASES

    if is_metadata_line(text):
        return True

    for phrase in phrases:
        if phrase in lower_text:
            return True

    if len(lower_text) < 20:
        return True

    return False


def deduplicate_paragraphs(parts, title):
    seen = set()
    deduped = []

    normalized_title = normalize_text_for_dedup(title)

    for part in parts:
        cleaned = clean_extracted_text(part)
        normalized = normalize_text_for_dedup(cleaned)

        if not normalized:
            continue

        if normalized == normalized_title:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        deduped.append(cleaned)

    return deduped