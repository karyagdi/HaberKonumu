# app/services/location_extractor.py

import re
import unicodedata


DISTRICT_ALIASES = {
    "İzmit": ["izmit"],
    "Gebze": ["gebze"],
    "Darıca": ["darica", "darıca"],
    "Çayırova": ["cayirova", "çayırova"],
    "Dilovası": ["dilovasi", "dilovası"],
    "Derince": ["derince"],
    "Körfez": ["korfez", "körfez"],
    "Gölcük": ["golcuk", "gölcük"],
    "Başiskele": ["basiskele", "başiskele"],
    "Kartepe": ["kartepe"],
    "Karamürsel": ["karamursel", "karamürsel"],
    "Kandıra": ["kandira", "kandıra"],
}

TITLE_DISTRICT_WEIGHT = 3
CONTENT_DISTRICT_WEIGHT = 1

LOCATION_PATTERNS = [
    r"\b[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9'\-]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9'\-]+){0,3}\s+(?:Mahallesi|Mah\.|Sokak|Sokağı|Cadde|Caddesi|Bulvar|Bulvarı|Kavşak|Kavşağı|Köprü|Köprüsü|Yolu|Mevkii|Mevki|Durağı|Otogar|Otogarı|Parkı|Meydanı)\b",
    r"\b[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9'\-]+(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9'\-]+){0,4}\s+(?:Sanayi Sitesi|Organize Sanayi Bölgesi|OSB)\b",
    r"\b(?:D-100|D100|TEM|Kuzey Marmara Otoyolu|E-5|E5)\b(?:\s+[A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü0-9'\-]+){0,3}",
]

DISTRICT_CONTEXT_PATTERNS = [
    r"\b(?:ilçesinde|ilcesinde|ilçesi|ilcesi|mevkiinde|mevkiinde|mevkiinde bulunan|mevkiinde yer alan)\b"
]


def normalize_text(text):
    text = text or ""
    text = text.lower()
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"[^\w\sçğıöşü']", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def count_keyword_matches(text, keyword):
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return len(re.findall(pattern, text))


def extract_district(title, content):
    normalized_title = normalize_text(title)
    normalized_content = normalize_text(content)

    district_scores = {}

    for district, aliases in DISTRICT_ALIASES.items():
        score = 0

        for alias in aliases:
            score += count_keyword_matches(normalized_title, alias) * TITLE_DISTRICT_WEIGHT
            score += count_keyword_matches(normalized_content, alias) * CONTENT_DISTRICT_WEIGHT

        district_scores[district] = score

    best_score = max(district_scores.values()) if district_scores else 0
    if best_score == 0:
        return ""

    best_districts = [
        district
        for district, score in district_scores.items()
        if score == best_score
    ]

    if len(best_districts) > 1:
        return ""

    return best_districts[0]


def clean_location_text(text):
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ,.-:;()[]")


def find_location_pattern(text):
    for pattern in LOCATION_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.UNICODE)
        if match:
            return clean_location_text(match.group(0))
    return ""


def extract_location_text(title, content, district):
    title = title or ""
    content = content or ""

    # 1) Önce başlıkta spesifik konum ara
    title_location = find_location_pattern(title)
    if title_location:
        return title_location

    # 2) Sonra içerikte spesifik konum ara
    content_location = find_location_pattern(content)
    if content_location:
        return content_location

    # 3) İlçe bulunduysa fallback olarak ilçe kullan
    if district:
        return district

    return ""


def extract_location_info(title, content):
    district = extract_district(title, content)
    location_text = extract_location_text(title, content, district)

    return {
        "district": district,
        "location_text": location_text
    }