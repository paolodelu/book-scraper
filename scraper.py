"""Book catalogue scraper.

Scrapes title, price, rating, availability and URL for every book on
books.toscrape.com (a sandbox site made for scraping practice) and saves
the result as CSV and/or Excel.

Usage:
    python scraper.py --pages 5 --format both --output books
"""

import argparse
import csv
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Font

BASE_URL = "https://books.toscrape.com/catalogue/page-{}.html"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
FIELDS = ["title", "price_gbp", "rating", "availability", "url"]
HEADERS = {"User-Agent": "Mozilla/5.0 (portfolio scraper demo)"}


def fetch_page(session, page_number, retries=3, delay=1.0):
    """Download one catalogue page. Returns (html, url) or (None, url) if missing."""
    url = BASE_URL.format(page_number)
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 404:
                return None, url
            response.raise_for_status()
            response.encoding = "utf-8"
            return response.text, url
        except requests.RequestException as exc:
            print(f"  [warn] page {page_number}, attempt {attempt}/{retries}: {exc}")
            time.sleep(delay * attempt)
    raise RuntimeError(f"Could not download page {page_number} after {retries} attempts")


def parse_page(html, page_url):
    """Extract book records from one page of HTML."""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for article in soup.select("article.product_pod"):
        link = article.select_one("h3 a")
        price_text = article.select_one("p.price_color").get_text(strip=True)
        rating_class = article.select_one("p.star-rating")["class"]
        rating_word = next((c for c in rating_class if c in RATINGS), None)
        books.append(
            {
                "title": link["title"],
                "price_gbp": float(re.sub(r"[^\d.]", "", price_text)),
                "rating": RATINGS.get(rating_word, 0),
                "availability": article.select_one("p.availability").get_text(strip=True),
                "url": urljoin(page_url, link["href"]),
            }
        )
    return books


def scrape(max_pages, delay):
    """Scrape up to max_pages pages and return a list of book dicts."""
    all_books = []
    with requests.Session() as session:
        for page in range(1, max_pages + 1):
            print(f"Scraping page {page}...")
            html, url = fetch_page(session, page)
            if html is None:
                print("No more pages.")
                break
            all_books.extend(parse_page(html, url))
            time.sleep(delay)  # be polite to the server
    return all_books


def save_csv(books, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(books)


def save_xlsx(books, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Books"
    ws.append(FIELDS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for book in books:
        ws.append([book[field] for field in FIELDS])
    widths = {"A": 55, "B": 12, "C": 10, "D": 16, "E": 70}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    wb.save(path)


def main():
    parser = argparse.ArgumentParser(description="Scrape books from books.toscrape.com")
    parser.add_argument("--pages", type=int, default=3, help="max pages to scrape (default 3, site has 50)")
    parser.add_argument("--format", choices=["csv", "xlsx", "both"], default="both")
    parser.add_argument("--output", default="books", help="output file name without extension")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    args = parser.parse_args()

    books = scrape(args.pages, args.delay)
    if not books:
        print("No data collected.")
        sys.exit(1)

    if args.format in ("csv", "both"):
        save_csv(books, f"{args.output}.csv")
        print(f"Saved {args.output}.csv")
    if args.format in ("xlsx", "both"):
        save_xlsx(books, f"{args.output}.xlsx")
        print(f"Saved {args.output}.xlsx")
    print(f"Done: {len(books)} books.")


if __name__ == "__main__":
    main()
