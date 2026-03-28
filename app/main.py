from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.mongo import get_news_collection


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="Kocaeli Haber Haritasi")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def serialize_news(doc):
    coordinates = doc.get("coordinates") or {}
    source = doc.get("source") or {}

    return {
        "id": str(doc.get("_id")),
        "news_type": doc.get("news_type", ""),
        "title": doc.get("title", ""),
        "content": doc.get("content", ""),
        "publish_date": doc.get("publish_date", ""),
        "location_text": doc.get("location_text", ""),
        "district": doc.get("district", ""),
        "coordinates": {
            "lat": coordinates.get("lat"),
            "lng": coordinates.get("lng"),
        },
        "source": {
            "site_name": source.get("site_name", ""),
            "url": source.get("url", ""),
        },
        "canonical_url": doc.get("canonical_url", ""),
    }


def build_query(news_type=None, district=None, start_date=None, end_date=None):
    query = {}

    if news_type:
        query["news_type"] = news_type

    if district:
        query["district"] = district

    if start_date or end_date:
        date_query = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        query["publish_date"] = date_query

    return query


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    context = {
        "request": request,
        "google_maps_api_key": google_maps_api_key
    }
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/news")
def get_news(
    news_type: str | None = Query(default=None),
    district: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
):
    collection = get_news_collection()

    query = build_query(
        news_type=news_type,
        district=district,
        start_date=start_date,
        end_date=end_date,
    )

    cursor = collection.find(query).sort("publish_date", -1)

    all_items = []
    map_items = []

    for doc in cursor:
        item = serialize_news(doc)
        all_items.append(item)

        lat = item["coordinates"]["lat"]
        lng = item["coordinates"]["lng"]

        if lat is None or lng is None:
            continue

        map_items.append(item)

    return {
        "total_count": len(all_items),
        "map_count": len(map_items),
        "items": map_items,
        "all_items": all_items,
    }


@app.get("/filters")
def get_filters():
    collection = get_news_collection()

    news_types = sorted([
        value for value in collection.distinct("news_type")
        if value
    ])

    districts = sorted([
        value for value in collection.distinct("district")
        if value
    ])

    return {
        "news_types": news_types,
        "districts": districts,
    }

