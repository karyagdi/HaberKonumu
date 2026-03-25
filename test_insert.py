# test_insert.py

from app.db.mongo import get_news_collection
from app.schemas.news_document import build_news_document


def main():
    collection = get_news_collection()

    news_document = build_news_document(
        title="Izmit'te trafik kazasi",
        content="Izmit ilcesinde iki aracin karistigi trafik kazasi meydana geldi.",
        news_type="traffic_accident",
        publish_date="2026-03-24",
        location_text="Izmit",
        district="Izmit",
        site_name="ornek_kocaeli_haber",
        url="https://example.com/izmit-trafik-kazasi",
        lat=None,
        lng=None
    )

    result = collection.insert_one(news_document)
    print("Kayit eklendi. MongoDB _id:", result.inserted_id)


if __name__ == "__main__":
    main()