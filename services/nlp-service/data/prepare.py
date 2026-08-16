"""
Data Preparation Script — NLP Service
Converts Kaggle CSV datasets into folder structure expected by train.py

Datasets expected in data/raw/:
  - emails.csv         (kaggle: balaka18/email-spam-classification-dataset-csv)
  - Phishing_Email.csv (kaggle: subhajournal/phishingemails)

Output:
  data/raw/prepared/phishing/     ← label 1
  data/raw/prepared/legitimate/   ← label 0

Run: python data/prepare.py
"""

import csv
import hashlib
from pathlib import Path
import sys

csv.field_size_limit(10 * 1024 * 1024)  # 10MB limit

RAW_DIR = Path("data/raw")
OUT_PHISHING = RAW_DIR / "prepared" / "phishing"
OUT_LEGIT = RAW_DIR / "prepared" / "legitimate"

OUT_PHISHING.mkdir(parents=True, exist_ok=True)
OUT_LEGIT.mkdir(parents=True, exist_ok=True)


def save_sample(text: str, label: int, index: int, source: str):
    """Save a single sample as a .txt file in the correct folder."""
    text = text.strip()
    if not text:
        return

    # Use hash as filename to avoid duplicates
    fname = hashlib.md5(f"{source}_{index}".encode()).hexdigest() + ".txt"
    folder = OUT_PHISHING if label == 1 else OUT_LEGIT

    with open(folder / fname, "w", encoding="utf-8") as f:
        f.write(text)


def process_emails_csv():
    """
    balaka18/email-spam-classification-dataset-csv
    Columns: the text content is spread across word columns
    Label column: 'Prediction' (1=spam, 0=ham)
    """
    path = RAW_DIR / "emails.csv"
    if not path.exists():
        print(f"[skip] {path} not found")
        return 0

    count = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            try:
                # Last column is 'Prediction', rest are word features
                label = int(row.get("Prediction", 0))
                # Join all word columns into text
                words = [v for k, v in row.items() if k != "Prediction"]
                text = " ".join(words)
                save_sample(text, label, i, "emails")
                count += 1
            except Exception:
                continue

    print(f"[emails.csv] processed {count} samples")
    return count


def process_phishing_email_csv():
    import pandas as pd
    path = RAW_DIR / "Phishing_Email.csv"
    if not path.exists():
        print(f"[skip] {path} not found")
        return 0

    count = 0
    df = pd.read_csv(path)
    for i, row in df.iterrows():
        try:
            email_type = str(row.get("Email Type", "")).strip()
            text = str(row.get("Email Text", "")).strip()
            if not text or text == "nan":
                continue
            label = 1 if email_type == "Phishing Email" else 0
            save_sample(text, label, i, "phishing_email")
            count += 1
        except Exception:
            continue

    print(f"[Phishing_Email.csv] processed {count} samples")
    return count

def main():
    print("Preparing training data...\n")

    total = 0
    total += process_emails_csv()
    total += process_phishing_email_csv()

    phishing_count = len(list(OUT_PHISHING.glob("*.txt")))
    legit_count = len(list(OUT_LEGIT.glob("*.txt")))

    print(f"\nDone — {total} total samples")
    print(f"  Phishing : {phishing_count}")
    print(f"  Legitimate: {legit_count}")
    print(f"\nOutput saved to {RAW_DIR / 'prepared'}")
    print("Now run: python train.py")


if __name__ == "__main__":
    main()