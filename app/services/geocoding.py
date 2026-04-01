import os
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY", "").strip()
GEOCODING_URL = "https://geocode-maps.yandex.ru/1.x/"

KOCAELI_CENTER_LAT = 40.7654
KOCAELI_CENTER_LNG = 29.9408

REQUEST_TIMEOUT = 15

KOCAELI_BOUNDS = {
    "north": 41.2,
    "south": 40.5,
    "west": 29.3,
    "east": 30.4,
}

DISTRICT_CENTER_COORDINATES = {
    "İzmit": (40.7654, 29.9408),
    "Gebze": (40.8028, 29.4307),
    "Darıca": (40.7706, 29.3705),
    "Çayırova": (40.8278, 29.3722),
    "Dilovası": (40.7876, 29.5447),
    "Derince": (40.7560, 29.8309),
    "Körfez": (40.7762, 29.7377),
    "Gölcük": (40.7167, 29.8167),
    "Başiskele": (40.6459, 29.9003),
    "Kartepe": (40.7525, 30.0272),
    "Karamürsel": (40.6913, 29.6165),
    "Kandıra": (41.0704, 30.1524),
}

GEOCODE_CACHE = {}


def turkish_safe_replace(text):
    """Türkçe karakterleri API'nin daha rahat anlayacağı küçük harf formuna çevirir."""
    if not text:
        return ""
    # Özellikle büyük İ ve I harflerindeki lower() hatalarını önlemek için manuel değişim
    replace_map = {
        "İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç",
        "i̇": "i" # Bazı durumlarda oluşan hatalı birleşimler için
    }
    for search, replace in replace_map.items():
        text = text.replace(search, replace)
    return text.lower()


def build_geocoding_query(location_text, district):
    location_text = (location_text or "").strip()
    district = (district or "").strip()

    if location_text and district:
        return f"{location_text}, {district}, Kocaeli, Türkiye"

    if location_text:
        return f"{location_text}, Kocaeli, Türkiye"

    if district:
        return f"{district}, Kocaeli, Türkiye"

    return "Kocaeli, Türkiye"


def is_within_kocaeli_bounds(lat, lng):
    if lat is None or lng is None:
        return False
    return (
        KOCAELI_BOUNDS["south"] <= lat <= KOCAELI_BOUNDS["north"]
        and KOCAELI_BOUNDS["west"] <= lng <= KOCAELI_BOUNDS["east"]
    )


def extract_lat_lon_from_yandex(item):
    try:
        pos = item.get("GeoObject", {}).get("Point", {}).get("pos")
        if pos:
            lon_str, lat_str = pos.split(" ")
            return float(lat_str), float(lon_str)
    except (ValueError, TypeError, AttributeError):
        pass
    return None, None


def result_looks_like_kocaeli(item):
    geo_object = item.get("GeoObject", {})
    name = str(geo_object.get("name", "")).lower()
    description = str(geo_object.get("description", "")).lower()

    if "kocaeli" in name or "kocaeli" in description:
        return True

    lat, lon = extract_lat_lon_from_yandex(item)
    if lat is not None and lon is not None:
        return is_within_kocaeli_bounds(lat, lon)

    return False


def get_district_center(district):
    district = (district or "").strip()
    return DISTRICT_CENTER_COORDINATES.get(district)


def get_kocaeli_center():
    return KOCAELI_CENTER_LAT, KOCAELI_CENTER_LNG


def get_fallback_coordinates(location_text, district):
    location_text = (location_text or "").strip()
    district = (district or "").strip()

    district_center = get_district_center(district)
    if district_center:
        return district_center

    if "kocaeli" in location_text.lower() or "kocaeli" in district.lower():
        return get_kocaeli_center()

    return None, None


def geocode_location(location_text, district):
    # Türkçe karakter temizliği yapılmış halleriyle işleme başla
    location_text = turkish_safe_replace(location_text or "")
    district = (district or "").strip()

    if not location_text and not district:
        return None, None

    cache_key = (location_text, district.lower())
    if cache_key in GEOCODE_CACHE:
        return GEOCODE_CACHE[cache_key]

    if district and (not location_text or location_text == district.lower()):
        result = get_district_center(district)
        if result:
            GEOCODE_CACHE[cache_key] = result
            return result

    query = build_geocoding_query(location_text, district)

    if not GEOCODING_API_KEY:
        result = get_fallback_coordinates(location_text, district)
        GEOCODE_CACHE[cache_key] = result
        return result

    try:
        # 1. AŞAMA: Kocaeli odaklı arama
        response = requests.get(
            GEOCODING_URL,
            params={
                "geocode": query,
                "apikey": GEOCODING_API_KEY,
                "format": "json",
                "results": 5
            },
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        feature_members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])

        # 2. AŞAMA: Kocaeli'de bulunamadıysa Türkiye geneli ara (SİLME MANTIĞI İÇİN)
        if not feature_members:
            broad_parts = [location_text]
            if district:
                broad_parts.append(district)
            
            broad_query = f"{', '.join(broad_parts)}, Türkiye"
            
            response_broad = requests.get(
                GEOCODING_URL,
                params={
                    "geocode": broad_query,
                    "apikey": GEOCODING_API_KEY,
                    "format": "json",
                    "results": 5
                },
                timeout=REQUEST_TIMEOUT
            )
            response_broad.raise_for_status()
            data_broad = response_broad.json()
            feature_members = data_broad.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])

        if feature_members:
            # Önce Kocaeli içinde olanı ara
            for item in feature_members:
                if result_looks_like_kocaeli(item):
                    lat, lon = extract_lat_lon_from_yandex(item)
                    if lat is not None and lon is not None:
                        result = (lat, lon)
                        GEOCODE_CACHE[cache_key] = result
                        return result

            # Bulunan ilk sonucu dön (Dışarıdaysa script silecek)
            lat, lon = extract_lat_lon_from_yandex(feature_members[0])
            if lat is not None and lon is not None:
                result = (lat, lon)
                GEOCODE_CACHE[cache_key] = result
                return result

    except (requests.RequestException, ValueError, TypeError):
        pass

    result = get_fallback_coordinates(location_text, district)
    GEOCODE_CACHE[cache_key] = result
    return result