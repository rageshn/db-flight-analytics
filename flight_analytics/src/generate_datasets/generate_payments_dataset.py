import csv
import json
import random
from datetime import date, datetime, time, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASETS = ROOT / "datasets"
BOOKINGS_PATH = DATASETS / "bookings.json"
OUTPUT_PATH = DATASETS / "payments.csv"
SEED = 20260926
PAYMENT_METHODS = ("Credit Card", "Debit Card", "PayPal", "Digital Wallet", "Bank Transfer")


def main() -> None:
    rng = random.Random(SEED)
    with BOOKINGS_PATH.open("r", encoding="utf-8-sig") as source:
        bookings = json.load(source)

    fields = [
        "payment_id",
        "booking_id",
        "payment_reference",
        "payment_method",
        "payment_amount",
        "currency",
        "payment_status",
        "transaction_time",
    ]

    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for index, booking in enumerate(bookings, start=1):
            transaction_date = date.fromisoformat(booking["booking_date"])
            transaction_datetime = datetime.combine(
                transaction_date,
                time(hour=rng.randrange(24), minute=rng.randrange(60), second=rng.randrange(60)),
                tzinfo=timezone.utc,
            )
            writer.writerow(
                {
                    "payment_id": f"PAY{index:09d}",
                    "booking_id": booking["booking_id"],
                    "payment_reference": f"PAYREF{index:010d}",
                    "payment_method": rng.choice(PAYMENT_METHODS),
                    "payment_amount": f"{float(booking['total_amount']):.2f}",
                    "currency": booking["currency"],
                    "payment_status": booking["payment_status"],
                    "transaction_time": transaction_datetime.isoformat().replace("+00:00", "Z"),
                }
            )

    print(f"Generated {len(bookings):,} payment rows at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()