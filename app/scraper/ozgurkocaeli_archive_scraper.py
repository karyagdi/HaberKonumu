import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.db.mongo import get_news_collection
from app.schemas.news_document import build_news_document
from app.services.news_prefilter import classify_news
from app.services.location_extractor import extract_location_info


BASE_URL = "https://www.ozgurkocaeli.com.tr"
START_ARCHIVE_URL = f"{BASE_URL}/arsiv"
SITE_NAME = "Özgür Kocaeli"
DAYS_TO_FETCH = 3

FAILED_URLS_PATH = Path("failed_urls_ozgurkocaeli.txt")

session = requests.Session()
session.headers.update({
    "User-Agent": "Python student project scraper",
    "Accept": "text/html,application/xhtml+xml",
})


def wait_between_requests():
    time.sleep(random.uniform(2.0, 3.5))


def fetch_html(url):
    try:
        response = session.get(url, timeout=(10, 25))
        status_code = response.status_code

        if status_code == 403:
            print(f"403 alindi: {url}")
            save_failed_url(url, "http_403")
            return None, "http_403"

        if status_code >= 400:
            print(f"HTTP hatasi {status_code}: {url}")
            save_failed_url(url, f"http_{status_code}")
            return None, f"http_{status_code}"

        wait_between_requests()
        return response.text, None

    except requests.Timeout:
        print(f"Timeout: {url}")
        save_failed_url(url, "timeout")
        return None, "timeout"
    except requests.RequestException as exc:
        print(f"Istek hatasi: {url} -> {exc}")
        save_failed_url(url, "request_error")
        return None, "request_error"


def save_failed_url(url, reason):
    with FAILED_URLS_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{reason}\t{url}\n")


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
    html, error = fetch_html(archive_url)
    if not html:
        return [], None, error

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

        text = a_tag.get_text(" ", strip=True)
        article_time = extract_time_from_text(text)

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
    previous_day_link = soup.find("a", string=lambda t: t and "ÖNCEKİ GÜN" in t.upper())

    if previous_day_link and previous_day_link.get("href"):
        previous_day_url = urljoin(BASE_URL, previous_day_link["href"])

    return article_items, previous_day_url, None


def extract_article_data(article_url, publish_date):
    html, error = fetch_html(article_url)
    if not html:
        return None, error

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1")
    if not title_tag:
        save_failed_url(article_url, "missing_title")
        return None, "missing_title"

    title = title_tag.get_text(" ", strip=True)
    if not title:
        save_failed_url(article_url, "empty_title")
        return None, "empty_title"

    content_parts = []

    for element in soup.find_all(["p", "h2", "blockquote"]):
        text = element.get_text(" ", strip=True)

        if not text:
            continue

        if text == title:
            continue

        if len(text) < 20:
            continue

        content_parts.append(text)

    content = "\n\n".join(content_parts).strip()

    if not content:
        save_failed_url(article_url, "empty_content")
        return None, "empty_content"

    return {
        "title": title,
        "content": content,
        "publish_date": publish_date,
        "url": article_url,
        "canonical_url": article_url,
    }, None


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
    FAILED_URLS_PATH.write_text("", encoding="utf-8")

    collection = get_news_collection()

    current_archive_url = START_ARCHIVE_URL
    all_article_items = []
    seen_article_urls = set()

    archive_http_fail_count = 0

    for day_index in range(DAYS_TO_FETCH):
        if not current_archive_url:
            break

        print(f"{day_index + 1}. gun arsivi geziliyor: {current_archive_url}")

        article_items, previous_day_url, error = get_archive_links_and_previous_page(current_archive_url)

        if error:
            archive_http_fail_count += 1
            print(f"Arsiv okunamadi: {current_archive_url}")
            break

        for item in article_items:
            if item["url"] not in seen_article_urls:
                seen_article_urls.add(item["url"])
                all_article_items.append(item)

        current_archive_url = previous_day_url

    print(f"Toplam bulunan benzersiz haber linki: {len(all_article_items)}")

    inserted_count = 0
    skipped_count = 0
    http_failed_count = 0
    parse_failed_count = 0
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
            parse_failed_count += 1
            save_failed_url(article_url, "missing_publish_date")
            print("Tarih bulunamadi")
            continue

        article_data, error = extract_article_data(article_url, publish_date)

        if error:
            if error.startswith("http_") or error in {"timeout", "request_error"}:
                http_failed_count += 1
            else:
                parse_failed_count += 1
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
            parse_failed_count += 1
            save_failed_url(article_url, f"mongo_error:{exc}")
            print(f"Mongo hatasi: {article_url}")

    print("Islem tamamlandi.")
    print(f"MongoDB'ye eklenen: {inserted_count}")
    print(f"Duplicate oldugu icin atlanan: {skipped_count}")
    print(f"On filtre nedeniyle elenen: {filtered_out_count}")
    print(f"Konum nedeniyle elenen: {location_filtered_out_count}")
    print(f"HTTP nedeniyle okunamayan: {http_failed_count}")
    print(f"Parse / veri nedeniyle okunamayan: {parse_failed_count}")
    print(f"Arsiv HTTP hatasi sayisi: {archive_http_fail_count}")


if __name__ == "__main__":
    run()