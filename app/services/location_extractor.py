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

KOCAELI_ALIASES = ["kocaeli"]

OUT_OF_KOCAELI_KEYWORDS = [
    "istanbul", "ankara", "izmir", "bursa", "sakarya", "yalova", "düzce", "adapazarı",
    "antalya", "trabzon", "konya", "eskişehir", "edirne", "tekirdağ", "çanakkale",
    "mersin", "adana", "gaziantep", "şanlıurfa", "diyarbakır", "samsun", "ordu",
    "giresun", "rize", "artvin", "muğla", "aydın", "balıkesir", "manisa", "denizli",
    "afyon", "kayseri", "sivas", "malatya", "erzurum", "van", "kars", "bitlis",
    "nevşehir", "kütahya", "uşak", "tokat", "çorum"
]

TITLE_DISTRICT_WEIGHT = 3
CONTENT_DISTRICT_WEIGHT = 1

# UZUNLUK SIRALAMASI DÜZELTİLDİ: Uzun olanlar önce eşleşir (Örn: Bulvarı > Bulvar)
LOCATION_KEYWORDS = (
    r"(?:Organize Sanayi Bölgesi|Cumhuriyet Bulvarı|Köprülü Kavşağı|Sanayi Sitesi|"
    r"Kent Meydanı|Mahallesi|Caddesi|Viyadüğü|Meydanı|Kavşağı|Sokağı|Köprüsü|Durağı|"
    r"Otogarı|Geçişi|Bulvarı|Mevkii|Parkı|Cadde|Sokak|Köprü|Yolu|OSB|Mah\.|Mevki|Otogar)"
)

TITLE_CASE_WORD = r"[A-ZÇĞİÖŞÜ][a-zçğıöşüA-ZÇĞİÖŞÜ0-9'\-]*"
EXTRACT_ENTITY_PATTERN = rf"\b(?:{TITLE_CASE_WORD}\s+){{1,6}}{LOCATION_KEYWORDS}\b"
# FALLBACK: Küçük harfle veya bozuk yazılmışsa sondaki kelimeyi bulup önceki 1-4 kelimeyi alan kural
FALLBACK_PATTERN = rf"(?i)\b(?:[\w'-]+\s+){{1,4}}{LOCATION_KEYWORDS}\b"

GENERAL_LOCATION_PATTERNS = [
    r"\b(?:D-100|D100|TEM|Kuzey Marmara Otoyolu|E-5|E5)\b",
    r"\bokul\b", r"\bfabrika\b", r"\bpark\b", r"\bhastane\b",
    r"\botogar\b", r"\bkampüs\b", r"\bstadyum\b", r"\bterminal\b", r"\bçarşı\b",
]

# GÜVENLİ NORMALİZASYON: Harfleri küçültmez, sadece boşluk ve tırnakları düzeltir
def normalize_text(text):
    text = text or ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("`", "'")
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def get_tr_regex(word):
    tr_chars = {
        'i': r'[iİıI]', 'ı': r'[ıIiİ]',
        'c': r'[cCçÇ]', 'ç': r'[cÇçC]',
        'g': r'[gGğĞ]', 'ğ': r'[gGğĞ]',
        'o': r'[oOöÖ]', 'ö': r'[oOöÖ]',
        's': r'[sSşŞ]', 'ş': r'[sSşŞ]',
        'u': r'[uUüÜ]', 'ü': r'[uUüÜ]'
    }
    pattern = ""
    for char in word.lower():
        if char in tr_chars:
            pattern += tr_chars[char]
        elif char.isalpha():
            pattern += f"[{char}{char.upper()}]"
        else:
            pattern += re.escape(char)
    return pattern

def score_district_in_text(text, alias):
    if not text:
        return 0
    score = 0
    base_pattern = get_tr_regex(alias)

    pattern_bare = r"\b" + base_pattern + r"\b"
    score += len(re.findall(pattern_bare, text)) * 1

    pattern_suffix = r"\b" + base_pattern + r"'?(?:te|ta|de|da|teki|taki|daki|deki|nin|nın|in|ın|ne|na|ye|ya|e|a|ten|tan|den|dan)\b"
    score += len(re.findall(pattern_suffix, text)) * 3

    pattern_context = r"\b" + base_pattern + r"\s+(?:[iİıI]l[çcÇC]esi|[iİıI]l[çcÇC]esinde|merkezi|merkezinde|ge[çcÇC][iİıI][şsŞS]i|ge[çcÇC][iİıI][şsŞS]inde)\b"
    score += len(re.findall(pattern_context, text)) * 5

    return score

def extract_district(title, content):
    combined_title = normalize_text(title)
    combined_content = normalize_text(content)
    
    district_scores = {}

    for district, aliases in DISTRICT_ALIASES.items():
        score = 0
        for alias in aliases:
            score += score_district_in_text(combined_title, alias) * TITLE_DISTRICT_WEIGHT
            score += score_district_in_text(combined_content, alias) * CONTENT_DISTRICT_WEIGHT
        
        if score > 0:
            district_scores[district] = score

    if not district_scores:
        return ""

    best_score = max(district_scores.values())
    best_districts = [d for d, s in district_scores.items() if s == best_score]

    if len(best_districts) > 1:
        return ""

    return best_districts[0]

def extract_specific_location(text):
    if not text:
        return ""
    
    # 1. Öncelik: Tam yapısal eşleşme (Büyük harflerle düzgün yazılmış olan)
    strict_matches = re.findall(EXTRACT_ENTITY_PATTERN, text)
    if strict_matches:
        return strict_matches[-1].strip()
    
    # 2. Fallback: Metin bozuk veya küçük harfliyse esnek eşleşme
    fallback_matches = re.findall(FALLBACK_PATTERN, text)
    if fallback_matches:
        return fallback_matches[-1].strip()
        
    return ""

def has_general_location_pattern(text):
    if not text:
        return False
    for pattern in GENERAL_LOCATION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE | re.UNICODE):
            return True
    return False

def contains_any_keyword(text, keywords):
    if not text:
        return False
    for kw in keywords:
        pattern = r"\b" + get_tr_regex(kw) + r"\b"
        if re.search(pattern, text):
            return True
    return False

def extract_location_text(title, content, district):
    norm_title = normalize_text(title)
    norm_content = normalize_text(content)

    title_specific = extract_specific_location(norm_title)
    if title_specific:
        return title_specific, "specific"

    content_specific = extract_specific_location(norm_content)
    if content_specific:
        return content_specific, "specific"

    if district:
        return district, "district"

    combined = f"{norm_title} {norm_content}"
    if contains_any_keyword(combined, KOCAELI_ALIASES):
        return "Kocaeli", "kocaeli"

    if has_general_location_pattern(norm_title) or has_general_location_pattern(norm_content):
        return "", "general"

    return "", "none"

def extract_district_from_location_text(location_text):
    for district, aliases in DISTRICT_ALIASES.items():
        for alias in aliases:
            if score_district_in_text(location_text, alias) > 0:
                return district
    return ""

def is_kocaeli_related(title, content, district):
    norm_title = normalize_text(title)
    norm_content = normalize_text(content)
    combined = f"{norm_title} {norm_content}"

    if district:
        return True

    if contains_any_keyword(combined, KOCAELI_ALIASES):
        return True

    if extract_specific_location(norm_title) or extract_specific_location(norm_content):
        return True

    if contains_any_keyword(combined, OUT_OF_KOCAELI_KEYWORDS):
        return False

    return False

def extract_location_info(title, content):
    district = extract_district(title, content)
    location_text, location_kind = extract_location_text(title, content, district)

    if not district and location_text:
        district = extract_district_from_location_text(location_text)

    is_kocaeli = is_kocaeli_related(title, content, district)

    if not is_kocaeli:
        return {
            "district": "",
            "location_text": "",
            "is_kocaeli": False,
            "should_skip": True
        }

    if location_kind == "general":
        if district:
            location_text = district
        else:
            location_text = "Kocaeli"

    if location_kind == "district":
        location_text = district

    if location_kind == "kocaeli":
        district = ""
        location_text = "Kocaeli"

    return {
        "district": district,
        "location_text": location_text,
        "is_kocaeli": True,
        "should_skip": False
    }