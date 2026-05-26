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
    {
        "hotel": "Poros Mood",
        "hotel_type": "own",
        "url": "https://www.booking.com/hotel/gr/poros-mood.html",
    },
    {
        "hotel": "Manessi City Boutique Hotel",
        "hotel_type": "competitor",
        "url": "https://www.booking.com/hotel/gr/manessi.html",
    },
    {
        "hotel": "Dionysos Hotel",
        "hotel_type": "competitor",
        "url": "https://www.booking.com/hotel/gr/dionysos-poros.html",
    },
    {
        "hotel": "Hotel Saron",
        "hotel_type": "competitor",
        "url": "https://www.booking.com/hotel/gr/saron.html",
    },
    {
        "hotel": "Dimitra Boutique Hotel",
        "hotel_type": "competitor",
        "url": "https://www.booking.com/hotel/gr/dimitra-poros-island.html",
    },
]

CSV_FILE = ROOT / "data" / "prices.csv"
REPORT_FILE = ROOT / "reports" / "latest_report.html"


def clean_price(text):
    if not text:
        return None

    text = text.replace(",", "").replace(".", "")
    numbers = re.findall(r"\d+", text)

    if not numbers:
        return None

    price = int(numbers[0])

    if 20 <= price <= 2000:
        return price

    return None


def extract_price_from_text(text):
    matches = re.findall(r"€\s?\d[\d,.]*|\d[\d,.]*\s?€", text)

    prices = []
    for match in matches:
        price = clean_price(match)
        if price:
            prices.append(price)

    if not prices:
        return None

    return min(prices)


def fetch_booking_price(page, hotel, checkin, checkout):
    print(f"Opening: {hotel['url']}")

    page.goto(hotel["url"], timeout=120000)
    page.wait_for_timeout(5000)

    try:
        page.click("button:has-text('Accept')", timeout=3000)
    except Exception:
        pass

    try:
        page.click("button:has-text('Search')", timeout=3000)
        page.wait_for_timeout(3000)
    except Exception:
        pass

    try:
        page.click('input[placeholder*="Check-in"]', timeout=5000)
        page.fill('input[placeholder*="Check-in"]', checkin)
        page.fill('input[placeholder*="Check-out"]', checkout)
        page.keyboard.press("Enter")
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"Date fill failed: {e}")

    try:
        page.click('button:has-text("Search")', timeout=5000)
        page.wait_for_timeout(10000)
    except Exception:
        pass

    try:
        buttons = page.locator("button:has-text('Show prices')")
        if buttons.count() > 0:
            buttons.first.click(timeout=5000)
            page.wait_for_timeout(8000)
    except Exception:
        pass

    safe_name = hotel["hotel"].replace(" ", "_").replace("/", "_")

    page.screenshot(
        path=str(ROOT / "debug" / f"{safe_name}.png"),
        full_page=True,
    )

    html = page.content()
    text = page.locator("body").inner_text()

    price = extract_price_from_text(text)

    if price:
        print(f"FOUND PRICE for {hotel['hotel']}: {price}")
    else:
        print(f"NO PRICE FOUND for {hotel['hotel']}")

    return price


def save_results(results):
    file_exists = CSV_FILE.exists()

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

        for row in results:
            writer.writerow(row)


def make_report(results):
    rows_html = ""

    for row in results:
        rows_html += f"""
        <tr>
            <td>{row[0]}</td>
            <td>{row[1]}</td>
            <td>{row[2]}</td>
            <td>{row[3]}</td>
            <td>{row[4]}</td>
            <td>{row[5]}</td>
            <td>{row[8] if row[8] else ""}</td>
            <td><a href="{row[9]}">Booking link</a></td>
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
                <th>Source</th>
                <th>Check-in</th>
                <th>Check-out</th>
                <th>Price EUR</th>
                <th>URL</th>
            </tr>
            {rows_html}
        </table>
    </body>
    </html>
    """

    REPORT_FILE.write_text(html, encoding="utf-8")


def main():
    run_date = datetime.now().strftime("%Y-%m-%d")

    checkin_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    checkout_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="en-GB")

        for hotel in HOTELS:
            try:
                price = fetch_booking_price(
                    page,
                    hotel,
                    checkin_date,
                    checkout_date,
                )

                results.append([
                    run_date,
                    hotel["hotel"],
                    hotel["hotel_type"],
                    "Booking",
                    checkin_date,
                    checkout_date,
                    1,
                    2,
                    price,
                    hotel["url"],
                ])

            except Exception as e:
                print(f"ERROR for {hotel['hotel']}: {e}")

                results.append([
                    run_date,
                    hotel["hotel"],
                    hotel["hotel_type"],
                    "Booking",
                    checkin_date,
                    checkout_date,
                    1,
                    2,
                    None,
                    hotel["url"],
                ])

            time.sleep(2)

        browser.close()

    save_results(results)
    make_report(results)

    print("DONE")


if __name__ == "__main__":
    main()
