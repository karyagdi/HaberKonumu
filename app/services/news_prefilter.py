# app/services/news_prefilter.py

import re
import unicodedata


CATEGORY_KEYWORDS = {
    "Trafik Kazası": {
        "high": [
            "trafik kazası",
            "zincirleme kaza",
            "maddi hasarlı kaza",
            "yaralamalı kaza",
            "ölümlü kaza",
            "trafik kazasında",
            "kaza yaptı"
        ],
        "medium": [
            "kaza",
            "çarpıştı",
            "çarptı",
            "devrildi",
            "yoldan çıktı",
            "kontrolden çıktı",
            "otomobil ile",
            "motosiklet ile",
            "iki araç",
            "araçlar çarpıştı"
        ]
    },
    "Yangın": {
        "high": [
            "yangın çıktı",
            "alevlere teslim",
            "ev yangını",
            "iş yeri yangını",
            "orman yangını",
            "fabrika yangını"
        ],
        "medium": [
            "yangın",
            "alev alev",
            "itfaiye ekipleri",
            "yoğun duman",
            "kül oldu",
            "yanarak kullanılamaz hale geldi"
        ]
    },
    "Elektrik Kesintisi": {
        "high": [
            "elektrik kesintisi",
            "elektrikler kesilecek",
            "planlı elektrik kesintisi",
            "bakım nedeniyle elektrik kesintisi",
            "enerji verilemeyecek"
        ],
        "medium": [
            "elektrik kesilecek",
            "kesinti yaşanacak",
            "şebeke çalışması",
            "bakım çalışması",
            "sedaş",
            "enerji kesintisi"
        ]
    },
    "Hırsızlık": {
        "high": [
            "hırsızlık olayı",
            "evden hırsızlık",
            "iş yerinden hırsızlık",
            "otomobil hırsızlığı",
            "hırsız yakalandı",
            "hırsızlık şüphelisi"
        ],
        "medium": [
            "hırsızlık",
            "hırsız",
            "çalındı",
            "çaldı",
            "soygun",
            "soydu",
            "gasp",
            "kamera görüntüsü"
        ]
    },
    "Kültürel Etkinlikler": {
        "high": [
            "kültürel etkinlik",
            "konser düzenlendi",
            "festival başladı",
            "sergi açıldı",
            "tiyatro gösterisi",
            "sahne aldı"
        ],
        "medium": [
            "konser",
            "festival",
            "sergi",
            "tiyatro",
            "etkinlik",
            "gösteri",
            "sanat etkinliği",
            "müzik dinletisi",
            "kültür sanat"
        ]
    }
}

CATEGORY_THRESHOLD = 4

TITLE_HIGH_WEIGHT = 4
TITLE_MEDIUM_WEIGHT = 2
CONTENT_HIGH_WEIGHT = 3
CONTENT_MEDIUM_WEIGHT = 1


def normalize_text(text):
    text = text or ""
    text = text.lower()
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = re.sub(r"[^\w\sçğıöşü]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def keyword_exists(text, keyword):
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return re.search(pattern, text) is not None


def calculate_category_score(title, content, category_rules):
    score = 0

    for keyword in category_rules["high"]:
        if keyword_exists(title, keyword):
            score += TITLE_HIGH_WEIGHT
        if keyword_exists(content, keyword):
            score += CONTENT_HIGH_WEIGHT

    for keyword in category_rules["medium"]:
        if keyword_exists(title, keyword):
            score += TITLE_MEDIUM_WEIGHT
        if keyword_exists(content, keyword):
            score += CONTENT_MEDIUM_WEIGHT

    return score


def classify_news(title, content):
    normalized_title = normalize_text(title)
    normalized_content = normalize_text(content)

    category_scores = {}

    for category_name, category_rules in CATEGORY_KEYWORDS.items():
        score = calculate_category_score(
            normalized_title,
            normalized_content,
            category_rules
        )
        category_scores[category_name] = score

    best_category = None
    best_score = 0

    for category_name, score in category_scores.items():
        if score > best_score:
            best_score = score
            best_category = category_name

    if best_score < CATEGORY_THRESHOLD:
        return None, 0

    best_categories = [
        category_name
        for category_name, score in category_scores.items()
        if score == best_score and score >= CATEGORY_THRESHOLD
    ]

    if len(best_categories) > 1:
        return None, 0

    return best_category, best_score