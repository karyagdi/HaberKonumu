import random
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.db.mongo import get_news_collection
from app.schemas.news_document import build_news_document
from app.services.news_prefilter import classify_news
from app.services.location_extractor import extract_location_info
from app.services.text_cleaning import (
    clean_extracted_text,
    deduplicate_paragraphs,
    is_noise_text,
)


BASE_URL = "https://www.cagdaskocaeli.com.tr"
START_ARCHIVE_URL = f"{BASE_URL}/arsiv"
SITE_NAME = "Çağdaş Kocaeli"
DAYS_TO_FETCH = 3

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": BASE_URL,
    "Connection": "keep-alive",
})


def wait_between_requests():
    time.sleep(random.uniform(1.5, 2.5))


def fetch_html(url):
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        wait_between_requests()
        return response.text
    except requests.RequestException as exc:
        print(f"Istek hatasi: {url} -> {exc}")
        return None


def normalize_archive_date(raw_date_text):
    raw_date_text = (raw_date_text or "").strip()

    parts = raw_date_text.split()
    if len(parts) != 3:
        return ""

    day, month, year = parts
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def find_archive_date(soup):
    for li_tag in soup.find_all("li"):
        text = li_tag.get_text(" ", strip=True)
        if re.fullmatch(r"\d{1,2}\s+\d{1,2}\s+\d{4}", text):
            return normalize_archive_date(text)
    return ""


def extract_time_from_link_text(link_text):
    link_text = (link_text or "").strip()
    match = re.match(r"^(\d{2}:\d{2})", link_text)
    if match:
        return match.group(1)
    return ""


def get_archive_links_and_previous_page(archive_url):
    html = fetch_html(archive_url)
    if not html:
        return [], None

    soup = BeautifulSoup(html, "html.parser")
    archive_date = find_archive_date(soup)

    article_items = []
    seen_urls = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()

        if not href:
            continue

        full_url = urljoin(BASE_URL, href)

        if "/haber/" not in full_url:
            continue

        if full_url in seen_urls:
            continue

        seen_urls.add(full_url)

        link_text = a_tag.get_text(" ", strip=True)
        article_time = extract_time_from_link_text(link_text)

        if archive_date and article_time:
            publish_date = f"{archive_date} {article_time}"
        elif archive_date:
            publish_date = archive_date
        else:
            publish_date = ""

        article_items.append({
            "url": full_url,
            "publish_date": publish_date
        })

    previous_day_url = None
    previous_day_link = soup.find("a", string=lambda text: text and "ÖNCEKİ GÜN" in text.upper())

    if previous_day_link and previous_day_link.get("href"):
        previous_day_url = urljoin(BASE_URL, previous_day_link.get("href"))

    return article_items, previous_day_url


def find_main_content_container(soup):
    selectors = [
        "article",
        ".news-detail",
        ".detail-content",
        ".post-content",
        ".content-detail",
        ".news-content",
        ".article-content",
        ".content",
    ]

    for selector in selectors:
        container = soup.select_one(selector)
        if container:
            return container

    return soup


def extract_clean_content_parts(container, title):
    raw_parts = []

    stop_phrases = {
        "Yazdır",
        "Muhabir",
        "Tüm Haberleri",
        "Yorumunuz",
        "Topluluk Kuralları",
        "Sosyal Sayfalar",
        "GALERİ",
        "GİRİŞ YAP",
        "Yorumlar",
        "Reklam seçeneklerimizi inceleyin",
        "Veri Politikası",
        "Kullanım Şartları",
        "Tüm Hakları Saklıdır",
        "KOGA A.Ş.",
        "Resmi İlanlar",
    }

    for element in container.find_all(["p", "h2", "blockquote", "li"]):
        text = clean_extracted_text(element.get_text(" ", strip=True))

        if not text:
            continue

        if text == title:
            continue

        lower_text = text.lower()

        if any(stop_phrase.lower() in lower_text for stop_phrase in stop_phrases):
            break

        if is_noise_text(text):
            continue

        raw_parts.append(text)

    return deduplicate_paragraphs(raw_parts, title)


def extract_article_data(article_url, publish_date):
    html = fetch_html(article_url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    if not title_tag:
        return None

    title = clean_extracted_text(title_tag.get_text(" ", strip=True))
    if not title:
        return None

    container = find_main_content_container(soup)
    content_parts = extract_clean_content_parts(container, title)

    content = "\n\n".join(content_parts).strip()

    if not content:
        return None

    return {
        "title": title,
        "content": content,
        "publish_date": publish_date,
        "url": article_url,
        "canonical_url": article_url
    }


def article_exists(collection, canonical_url):
    return collection.find_one({"canonical_url": canonical_url}) is not None


def save_article(collection, article_data):
    news_document = build_news_document(
        title=article_data["title"],
        content=article_data["content"],
        news_type=article_data["news_type"],
        publish_date=article_data["publish_date"],
        location_text=article_data["location_text"],
        district=article_data["district"],
        site_name=SITE_NAME,
        url=article_data["url"],
        canonical_url=article_data["canonical_url"],
        lat=None,
        lng=None
    )
    collection.insert_one(news_document)
    return True


def run():
    collection = get_news_collection()

    current_archive_url = START_ARCHIVE_URL
    all_article_items = []
    seen_article_urls = set()

    for day_index in range(DAYS_TO_FETCH):
        if not current_archive_url:
            break

        print(f"{day_index + 1}. gun arsivi geziliyor: {current_archive_url}")

        article_items, previous_day_url = get_archive_links_and_previous_page(current_archive_url)

        if not article_items:
            print(f"Arsiv sayfasindan link alinamadi: {current_archive_url}")

        for item in article_items:
            if item["url"] not in seen_article_urls:
                seen_article_urls.add(item["url"])
                all_article_items.append(item)

        current_archive_url = previous_day_url

    print(f"Toplam bulunan benzersiz haber linki: {len(all_article_items)}")

    inserted_count = 0
    skipped_count = 0
    failed_count = 0
    filtered_out_count = 0
    location_filtered_out_count = 0

    for index, item in enumerate(all_article_items, start=1):
        article_url = item["url"]
        publish_date = item["publish_date"]

        print(f"Isleniyor ({index}/{len(all_article_items)}): {article_url}")

        try:
            if article_exists(collection, article_url):
                skipped_count += 1
                print(f"Duplicate oldugu icin atlandi: {article_url}")
                continue

            if not publish_date:
                failed_count += 1
                print(f"Tarih bulunamadi, atlandi: {article_url}")
                continue

            article_data = extract_article_data(article_url, publish_date)

            if not article_data:
                failed_count += 1
                print(f"Okunamadi veya parse edilemedi: {article_url}")
                continue

            news_type, score = classify_news(
                article_data["title"],
                article_data["content"]
            )

            if not news_type:
                filtered_out_count += 1
                print(f"On filtreye takildi, DB'ye yazilmadi: {article_url}")
                continue

            article_data["news_type"] = news_type

            location_info = extract_location_info(
                article_data["title"],
                article_data["content"]
            )

            if location_info["should_skip"]:
                location_filtered_out_count += 1
                print(f"Konum/Kocaeli iliskisi nedeniyle DB'ye yazilmadi: {article_url}")
                continue

            article_data["district"] = location_info["district"]
            article_data["location_text"] = location_info["location_text"]

            save_article(collection, article_data)
            inserted_count += 1
            print(
                f"Kaydedildi -> {news_type} (skor: {score}) | "
                f"district={article_data['district']} | "
                f"location={article_data['location_text']}"
            )

        except Exception as exc:
            failed_count += 1
            print(f"Hata: {article_url} -> {exc}")

    print("Islem tamamlandi.")
    print(f"MongoDB'ye eklenen: {inserted_count}")
    print(f"Duplicate oldugu icin atlanan: {skipped_count}")
    print(f"On filtre nedeniyle elenen: {filtered_out_count}")
    print(f"Konum nedeniyle elenen: {location_filtered_out_count}")
    print(f"Okunamayan / parse edilemeyen: {failed_count}")


if __name__ == "__main__":
    run()