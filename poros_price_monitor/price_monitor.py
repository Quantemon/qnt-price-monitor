import csv
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "reports").mkdir(exist_ok=True)
(ROOT / "debug").mkdir(exist_ok=True)

CSV_FILE = ROOT / "data" / "prices.csv"
REPORT_FILE = ROOT / "reports" / "latest_report.html"

HOTELS = [
    {"hotel": "Poros Mood", "hotel_type": "own"},
    {"hotel": "Manessi City Boutique Hotel", "hotel_type": "competitor"},
    {"hotel": "Dionysos Hotel", "hotel_type": "competitor"},
    {"hotel": "Hotel Saron", "hotel_type": "competitor"},
    {"hotel": "Dimitra Boutique Hotel", "hotel_type": "competitor"},
]


def clean_price(text):
    if not text:
        return None

    text = text.replace(",", "").replace(".", "")
    nums = re.findall(r"\d+", text)

    if not nums:
        return None

    price = int(nums[0])
    return price if 40 <= price <= 2000 else None


def build_booking_search_url(hotel_name, checkin, checkout):
    params = {
        "ss": f"{hotel_name} Poros Greece",
        "checkin": checkin,
        "checkout": checkout,
        "group_adults": "2",
        "group_children": "0",
        "no_rooms": "1",
        "selected_currency": "EUR",
        "lang": "en-gb",
    }

    return "https://www.booking.com/searchresults.html?" + urlencode(params)


def extract_price_from_page(page):
    selectors = [
        '[data-testid="price-and-discounted-price"]',
        '[data-testid="availability-rate-information"]',
        'span:has-text("€")',
    ]

    for selector in selectors:
        try:
            items = page.locator(selector)
            count = items.count()

            for i in range(min(count, 10)):
                text = items.nth(i).inner_text(timeout=3000)
                price = clean_price(text)
                if price:
                    return price
        except Exception:
            pass

    text = page.locator("body").inner_text()
    matches = re.findall(r"€\s?\d[\d,.]*|\d[\d,.]*\s?€|EUR\s?\d[\d,.]*", text)

    prices = []
    for match in matches:
        p = clean_price(match)
        if p:
            prices.append(p)

    return min(prices) if prices else None


def fetch_booking_price(page, hotel, checkin, checkout):
    url = build_booking_search_url(hotel["hotel"], checkin, checkout)

    print(f"Opening: {url}")

    page.goto(url, timeout=120000)

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(10000)

    try:
        page.click('button:has-text("Accept")', timeout=3000)
        page.wait_for_timeout(2000)
    except:
        pass

    page.mouse.wheel(0, 4000)
    page.wait_for_timeout(4000)

    body = page.locator("body").inner_text()

    matches = re.findall(r'€\s?\d+', body)

    prices = []

    for match in matches:
        nums = re.findall(r'\d+', match)

        if nums:
            p = int(nums[0])

            if 40 <= p <= 2000:
                prices.append(p)

    safe = hotel["hotel"].replace(" ", "_")

    page.screenshot(
        path=str(ROOT / "debug" / f"{safe}.png"),
        full_page=True
    )

    if prices:
        price = min(prices)
        print(f"FOUND PRICE {hotel['hotel']}: {price}")
        return price, url

    print(f"NO PRICE FOUND {hotel['hotel']}")
    return None, url

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "run_date",
                "hotel",
                "hotel_type",
                "source",
                "checkin",
                "checkout",
                "nights",
                "adults",
                "price_eur",
                "url",
            ])

        writer.writerows(results)


def make_report(results):
    rows = ""

    for r in results:
        rows += f"""
        <tr>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td>{r[2]}</td>
            <td>{r[4]}</td>
            <td>{r[5]}</td>
            <td>{r[8] if r[8] else ""}</td>
            <td><a href="{r[9]}">Booking</a></td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Poros Price Monitor</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 32px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; }}
            th {{ background: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Poros Price Monitor</h1>
        <h2>Τελευταίες τιμές Booking</h2>
        <table>
            <tr>
                <th>Run date</th>
                <th>Hotel</th>
                <th>Type</th>
                <th>Check-in</th>
                <th>Check-out</th>
                <th>Price EUR</th>
                <th>URL</th>
            </tr>
            {rows}
        </table>
    </body>
    </html>
    """

    REPORT_FILE.write_text(html, encoding="utf-8")


def main():
    run_date = datetime.now().strftime("%Y-%m-%d")
    checkin = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    checkout = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="en-GB")

        for hotel in HOTELS:
            try:
                price, url = fetch_booking_price(page, hotel, checkin, checkout)
            except Exception as e:
                print(f"ERROR for {hotel['hotel']}: {e}")
                price = None
                url = build_booking_search_url(hotel["hotel"], checkin, checkout)

            results.append([
                run_date,
                hotel["hotel"],
                hotel["hotel_type"],
                "Booking",
                checkin,
                checkout,
                1,
                2,
                price,
                url,
            ])

            time.sleep(2)

        browser.close()

    save_results(results)
    make_report(results)
    print("DONE")


if __name__ == "__main__":
    main()
