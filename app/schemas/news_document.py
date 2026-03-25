# app/schemas/news_document.py

def build_news_document(
    title,
    content,
    news_type,
    publish_date,
    location_text,
    district,
    site_name,
    url,
    canonical_url,
    lat=None,
    lng=None
):
    title = (title or "").strip()
    content = (content or "").strip()
    news_type = (news_type or "").strip()
    publish_date = (publish_date or "").strip()
    location_text = (location_text or "").strip()
    district = (district or "").strip()
    site_name = (site_name or "").strip()
    url = (url or "").strip()
    canonical_url = (canonical_url or "").strip()

    if not title:
        raise ValueError("title alani bos olamaz")

    if not content:
        raise ValueError("content alani bos olamaz")

    if not news_type:
        raise ValueError("news_type alani bos olamaz")

    if not publish_date:
        raise ValueError("publish_date alani bos olamaz")

    if not site_name:
        raise ValueError("site_name alani bos olamaz")

    if not url:
        raise ValueError("url alani bos olamaz")

    if not canonical_url:
        raise ValueError("canonical_url alani bos olamaz")

    return {
        "title": title,
        "content": content,
        "news_type": news_type,
        "publish_date": publish_date,
        "location_text": location_text,
        "district": district,
        "coordinates": {
            "lat": lat,
            "lng": lng
        },
        "source": {
            "site_name": site_name,
            "url": url
        },
        "canonical_url": canonical_url
    }