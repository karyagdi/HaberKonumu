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


BASE_URL = "https://www.bizimyaka.com"
START_ARCHIVE_URL = f"{BASE_URL}/arsiv"
SITE_NAME = "Bizim Yaka"
DAYS_TO_FETCH = 3

session = requests.Session()
session.headers.update({
    "User-Agent": "Python student project scraper",
    "Accept": "text/html,application/xhtml+xml",
})


def wait_between_requests():
    time.sleep(random.uniform(1.0, 1.5))


def fetch_html(url):
    try:
        response = session.get(url, timeout=(10, 25))
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
    for element in soup.find_all(["li", "div", "span", "p", "strong"]):
        text = element.get_text(" ", strip=True)
        if re.fullmatch(r"\d{1,2}\s+\d{1,2}\s+\d{4}", text):
            return normalize_archive_date(text)
    return ""


def extract_time_from_text(text):
    text = (text or "").strip()
    match = re.search(r"\b(\d{2}\s*:\s*\d{2})\b", text)
    if not match:
        return ""
    return match.group(1).replace(" ", "")


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
        article_time = extract_time_from_text(link_text)

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


def extract_article_publish_date(soup):
    page_text = soup.get_text("\n", strip=True)

    match = re.search(
        r"(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\s*-\s*\d{2}:\d{2})",
        page_text
    )
    if match:
        return match.group(1)

    return ""


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
        "Bu haberi kaçırmayın",
        "Topluluk Kuralları",
        "GİRİŞ YAP",
        "KOGA A.Ş. MEDYA GRUBU",
        "Reklam seçeneklerimizi inceleyin",
        "Veri Politikası",
        "Kullanım Şartları",
        "Tüm Hakları Saklıdır",
        "Yorumunuz",
        "Yorumlar",
        "Sosyal Sayfalar",
        "GALERİ",
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

    detail_publish_date = extract_article_publish_date(soup)
    if detail_publish_date:
        publish_date = detail_publish_date

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
            print(f"Arsivden link alinamadi: {current_archive_url}")
            break

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

        if article_exists(collection, article_url):
            skipped_count += 1
            print("Duplicate oldugu icin atlandi")
            continue

        if not publish_date:
            failed_count += 1
            print("Tarih bulunamadi")
            continue

        article_data = extract_article_data(article_url, publish_date)

        if not article_data:
            failed_count += 1
            print("Detay sayfasi okunamadi veya parse edilemedi")
            continue

        news_type, score = classify_news(
            article_data["title"],
            article_data["content"]
        )

        if not news_type:
            filtered_out_count += 1
            print("On filtreye takildi, DB'ye yazilmadi")
            continue

        article_data["news_type"] = news_type

        location_info = extract_location_info(
            article_data["title"],
            article_data["content"]
        )

        if location_info["should_skip"]:
            location_filtered_out_count += 1
            print("Konum/Kocaeli iliskisi nedeniyle DB'ye yazilmadi")
            continue

        article_data["location_text"] = location_info["location_text"]
        article_data["district"] = location_info["district"]

        try:
            save_article(collection, article_data)
            inserted_count += 1
            print(
                f"Kaydedildi -> {news_type} (skor: {score}) | "
                f"district={article_data['district']} | "
                f"location={article_data['location_text']}"
            )
        except Exception as exc:
            failed_count += 1
            print(f"Mongo kayit hatasi: {exc}")

    print("Islem tamamlandi.")
    print(f"MongoDB'ye eklenen: {inserted_count}")
    print(f"Duplicate oldugu icin atlanan: {skipped_count}")
    print(f"On filtre nedeniyle elenen: {filtered_out_count}")
    print(f"Konum nedeniyle elenen: {location_filtered_out_count}")
    print(f"Okunamayan / parse edilemeyen: {failed_count}")


if __name__ == "__main__":
    run()