import os
from pathlib import Path

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY", "").strip()
GEOCODING_URL = "https://geocode.maps.co/search"

KOCAELI_CENTER_LAT = 40.7654
KOCAELI_CENTER_LNG = 29.9408

REQUEST_TIMEOUT = 15


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


def geocode_location(location_text, district):
    location_text = (location_text or "").strip()
    district = (district or "").strip()

    if not location_text and not district:
        return None, None

    query = build_geocoding_query(location_text, district)

    if not GEOCODING_API_KEY:
        if not location_text and district.lower() == "kocaeli":
            return KOCAELI_CENTER_LAT, KOCAELI_CENTER_LNG
        return None, None

    try:
        response = requests.get(
            GEOCODING_URL,
            params={
                "q": query,
                "api_key": GEOCODING_API_KEY
            },
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()

        data = response.json()

        if data and isinstance(data, list):
            first_item = data[0]
            lat = first_item.get("lat")
            lon = first_item.get("lon")

            if lat is not None and lon is not None:
                return float(lat), float(lon)

    except (requests.RequestException, ValueError, TypeError):
        pass

    if not location_text and district.lower() == "kocaeli":
        return KOCAELI_CENTER_LAT, KOCAELI_CENTER_LNG

    return None, None
