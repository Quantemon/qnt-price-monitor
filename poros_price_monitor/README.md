# Poros Price Monitor

Ημερήσια παρακολούθηση τιμών για Poros Mood και ανταγωνιστές από Booking και official websites.

## Τι κάνει
- Τρέχει κάθε μέρα με GitHub Actions ή τοπικά με cron.
- Ψάχνει τιμές για τα επόμενα N check-in dates.
- Αποθηκεύει αποτελέσματα σε `data/prices.csv`.
- Δημιουργεί ημερήσιο report `reports/latest_report.html`.

## Γρήγορη εγκατάσταση
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python price_monitor.py
```

## Ρύθμιση
Άνοιξε `config.yaml` και άλλαξε adults/nights/lookahead_days.

## Αυτόματη καθημερινή εκτέλεση
Ανέβασε τον φάκελο σε GitHub repository. Το `.github/workflows/daily.yml` τρέχει κάθε μέρα.
