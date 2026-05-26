import asyncio, re, yaml
from pathlib import Path
from datetime import date, timedelta
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

ROOT = Path(__file__).parent
for p in ["data", "reports", "debug"]:
    (ROOT / p).mkdir(exist_ok=True)

PRICE_RE = re.compile(r"(?:€|EUR)\s*([0-9][0-9\.,]*)|([0-9][0-9\.,]*)\s*(?:€|EUR)", re.I)

def add_booking_params(url, checkin, checkout, adults=2, children=0):
    parsed = urlparse(url)
    q = dict(parse_qsl(parsed.query))
    q.update({
        "checkin": checkin.isoformat(),
        "checkout": checkout.isoformat(),
        "group_adults": str(adults),
        "group_children": str(children),
        "no_rooms": "1",
        "selected_currency": "EUR",
        "lang": "en-gb",
    })
    return urlunparse(parsed._replace(query=urlencode(q)))

def extract_lowest_price(text):
    vals = []
    for m in PRICE_RE.finditer(text.replace("\xa0", " ")):
        raw = m.group(1) or m.group(2)
        try:
            price = float(raw.replace(".", "").replace(",", "."))
            if 20 <= price <= 2000:
                vals.append(price)
        except ValueError:
            pass
    return min(vals) if vals else None

async def fetch_price(page, url, label, timeout_seconds=35):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds*1000)
        await page.wait_for_load_state("networkidle")
await page.wait_for_timeout(5000)
        html = await page.content()
        text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", label)[:80]
(ROOT / "debug" / f"{safe}.html").write_text(html, encoding="utf-8")
await page.screenshot(path=str(ROOT / "debug" / f"{safe}.png"), full_page=True)
        if price is None:
            safe = re.sub(r"[^a-zA-Z0-9]+", "_", label)[:80]
            (ROOT / "debug" / f"{safe}.html").write_text(html, encoding="utf-8")
            await page.screenshot(path=str(ROOT / "debug" / f"{safe}.png"), full_page=True)
        return price
    except Exception as e:
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", label)[:80]
        (ROOT / "debug" / f"{safe}_error.txt").write_text(str(e), encoding="utf-8")
        return None

def date_pairs(settings):
    today = date.today()
    for i in range(int(settings["lookahead_days"])):
        checkin = today + timedelta(days=i+1)
        if checkin.weekday() in set(settings.get("checkin_weekdays", list(range(7)))):
            yield checkin, checkin + timedelta(days=int(settings["nights"]))

async def main():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    s = cfg["settings"]
    rows = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=bool(s.get("headless", True)))
        context = await browser.new_context(locale="en-GB")
        page = await context.new_page()
        for checkin, checkout in date_pairs(s):
            for hotel in cfg["hotels"]:
                if hotel.get("booking_url"):
                    url = add_booking_params(hotel["booking_url"], checkin, checkout, s.get("adults", 2), s.get("children", 0))
                    price = await fetch_price(page, url, f"{hotel['name']}_booking_{checkin}", s["timeout_seconds"])
                    rows.append({"run_date": date.today().isoformat(), "hotel": hotel["name"], "hotel_type": hotel.get("type","competitor"), "source": "Booking", "checkin": checkin.isoformat(), "checkout": checkout.isoformat(), "nights": s["nights"], "adults": s["adults"], "price_eur": price, "url": url})
                official = hotel.get("official_booking_engine") or hotel.get("official_url")
                if official:
                    price = await fetch_price(page, official, f"{hotel['name']}_official_{checkin}", s["timeout_seconds"])
                    rows.append({"run_date": date.today().isoformat(), "hotel": hotel["name"], "hotel_type": hotel.get("type","competitor"), "source": "Official", "checkin": checkin.isoformat(), "checkout": checkout.isoformat(), "nights": s["nights"], "adults": s["adults"], "price_eur": price, "url": official})
        await browser.close()

    out = ROOT / "data" / "prices.csv"
    df = pd.DataFrame(rows)
    if out.exists():
        df = pd.concat([pd.read_csv(out), df], ignore_index=True)
    df.to_csv(out, index=False)
    make_report(df)

def make_report(df):
    latest = df[df["run_date"] == df["run_date"].max()].copy()
    own = latest[(latest.hotel_type=="own") & latest.price_eur.notna()]
    comp = latest[(latest.hotel_type!="own") & latest.price_eur.notna()]
    summary = []
    for checkin in sorted(latest["checkin"].unique()):
        op = own[own.checkin==checkin]["price_eur"]
        cp = comp[comp.checkin==checkin]["price_eur"]
        if len(op) and len(cp):
            summary.append({"checkin": checkin, "your_min_price": op.min(), "competitor_min": cp.min(), "competitor_avg": round(cp.mean(),2),
                            "recommended_action": "Αύξηση/κράτα" if op.min() < cp.mean()*0.95 else "Έλεγξε για μείωση" if op.min() > cp.mean()*1.10 else "OK"})
    html = f"""<html><head><meta charset="utf-8"><title>Poros Price Monitor</title>
<style>body{{font-family:Arial;margin:32px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px}}th{{background:#f3f3f3}}</style></head>
<body><h1>Poros Price Monitor</h1><h2>Προτεινόμενες κινήσεις</h2>{pd.DataFrame(summary).to_html(index=False) if summary else "<p>Δεν βρέθηκαν αρκετές τιμές.</p>"}<h2>Τελευταίες τιμές</h2>{latest.sort_values(["checkin","hotel","source"]).to_html(index=False)}</body></html>"""
    (ROOT / "reports" / "latest_report.html").write_text(html, encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(main())
