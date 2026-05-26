import csv
import re
import time
from pathlib import Path
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "reports").mkdir(exist_ok=True)
(ROOT / "debug").mkdir(exist_ok=True)

HOTELS = [
    {"hotel": "Poros Mood", "hotel_type": "own", "url": "https://www.booking.com/hotel/gr/poros-mood.html"},
    {"hotel": "Manessi City Boutique Hotel", "hotel_type": "competitor", "url": "https://www.booking.com/hotel/gr/manessi.html"},
    {"hotel": "Dionysos Hotel", "hotel_type": "competitor", "url": "https://www.booking.com/hotel/gr/dionysos-poros.html"},
    {"hotel": "Hotel Saron", "hotel_type": "competitor", "url": "https://www.booking.com/hotel/gr/saron.html"},
    {"hotel": "Dimitra Boutique Hotel", "hotel_type": "competitor", "url": "https://www.booking.com/hotel/gr/dimitra-poros-island.html"},
]

CSV_FILE = ROOT / "data" / "prices.csv"
REPORT_FILE = ROOT / "reports" / "latest_report.html"


def clean_price(text):
    text = text.replace(",", "").replace(".", "")
    numbers = re.findall(r"\d+", text)
    if not numbers:
        return None
    price = int(numbers[0])
    return price if 40 <= price <= 2000 else None


def extract_price_from_text(text):
    matches = re.findall(
        r"(?:€|EUR|£)\s?\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s?(?:€|EUR|£)",
        text,
    )
    prices = [clean_price(m) for m in matches]
    prices = [p for p in prices if p]
    return min(prices) if prices else None


def fetch_booking_price(page, hotel, checkin, checkout):
    url = (
        f"{hotel['url']}?"
        f"checkin={checkin}&checkout={checkout}"
        f"&group_adults=2&group_children=0&no_rooms=1"
        f"&selected_currency=EUR&lang=en-gb"
    )

    page.goto(url, timeout=120000)
    page.wait_for_timeout(6000)

    try:
        page.click("button:has-text('Accept')", timeout=3000)
    except Exception:
        pass

    try:
        page.click("button:has-text('Search')", timeout=5000)
        page.wait_for_timeout(8000)
    except Exception:
        pass

    try:
        buttons = page.locator("button:has-text('Show prices')")
        if buttons.count() > 0:
            buttons.first.click(timeout=5000)
            page.wait_for_timeout(8000)
    except Exception:
        pass

    safe = hotel["hotel"].replace(" ", "_").replace("/", "_")
    page.screenshot(path=str(ROOT / "debug" / f"{safe}.png"), full_page=True)

    text = page.locator("body").inner_text()
    return extract_price_from_text(text)


def save_results(results):
    file_exists = CSV_FILE.exists()

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "run_date", "hotel", "hotel_type", "source",
                "checkin", "checkout", "nights", "adults",
                "price_eur", "url"
            ])

        writer.writerows(results)


def make_report(results):
    rows = ""
    for r in results:
        rows += f"""
        <tr>
            <td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td>
            <td>{r[4]}</td><td>{r[5]}</td>
            <td>{r[8] if r[8] else ""}</td>
            <td><a href="{r[9]}">Booking</a></td>
        </tr>
        """

    REPORT_FILE.write_text(f"""
    <html><head><meta charset="utf-8"><title>Poros Price Monitor</title></head>
    <body>
    <h1>Poros Price Monitor</h1>
    <table border="1" cellpadding="6">
    <tr><th>Run date</th><th>Hotel</th><th>Type</th><th>Check-in</th><th>Check-out</th><th>Price EUR</th><th>URL</th></tr>
    {rows}
    </table>
    </body></html>
    """, encoding="utf-8")


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
                price = fetch_booking_price(page, hotel, checkin, checkout)
            except Exception as e:
                print(f"ERROR {hotel['hotel']}: {e}")
                price = None

            results.append([
                run_date, hotel["hotel"], hotel["hotel_type"], "Booking",
                checkin, checkout, 1, 2, price, hotel["url"]
            ])

            time.sleep(2)

        browser.close()

    save_results(results)
    make_report(results)
    print("DONE")


if __name__ == "__main__":
    main()
