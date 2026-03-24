def build_news_document(
    title,
    content,
    news_type,
    publish_date,
    location_text,
    district,
    lat,
    lng,
    site_name,
    url
):
    if not title:
        raise ValueError("title alani bos olamaz")

    if not content:
        raise ValueError("content alani bos olamaz")

    if not news_type:
        raise ValueError("news_type alani bos olamaz")

    if not publish_date:
        raise ValueError("publish_date alani bos olamaz")

    if not location_text:
        raise ValueError("location_text alani bos olamaz")

    if lat is None or lng is None:
        raise ValueError("coordinates alanlari bos olamaz")

    if not site_name:
        raise ValueError("site_name alani bos olamaz")

    if not url:
        raise ValueError("url alani bos olamaz")

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
        "primary_source": {
            "site_name": site_name,
            "url": url
        },
        "all_sources": [
            {
                "site_name": site_name,
                "url": url
            }
        ],
        "canonical_url": url
    }