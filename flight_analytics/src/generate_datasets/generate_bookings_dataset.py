import csv
import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PASSENGERS_PATH = ROOT / "datasets" / "passengers.csv"
PRICING_PATH = ROOT / "datasets" / "flight_pricing.csv"
OUTPUT_PATH = ROOT / "datasets" / "bookings.json"
BOOKING_COUNT = 100_000
SEED = 20260926
PNR_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def main() -> None:
    rng = random.Random(SEED)
    passengers = read_csv(PASSENGERS_PATH)
    fares = read_csv(PRICING_PATH)
    if not passengers or not fares:
        raise ValueError("Passenger and flight pricing datasets must both be non-empty")

    bookings: list[dict[str, object]] = []
    used_pnrs: set[str] = set()

    for index in range(1, BOOKING_COUNT + 1):
        passenger = rng.choice(passengers)
        fare = rng.choice(fares)
        departure = datetime.fromisoformat(
            fare["departure_utc"].replace("Z", "+00:00")
        ).date()
        earliest_booking_date = departure - timedelta(days=180)
        booking_date = earliest_booking_date + timedelta(
            days=rng.randint(0, (departure - earliest_booking_date).days - 1)
        )

        booking_status = rng.choices(
            ["Confirmed", "Pending", "Cancelled"], weights=[85, 8, 7], k=1
        )[0]
        if booking_status == "Confirmed":
            payment_status = rng.choices(["Paid", "Pending"], weights=[95, 5], k=1)[0]
        elif booking_status == "Pending":
            payment_status = rng.choices(["Pending", "Failed"], weights=[85, 15], k=1)[0]
        else:
            payment_status = rng.choices(["Refunded", "Failed"], weights=[80, 20], k=1)[0]

        while True:
            pnr = "".join(rng.choices(PNR_ALPHABET, k=8))
            if pnr not in used_pnrs:
                used_pnrs.add(pnr)
                break

        amount = Decimal(fare["total_cost"])
        bookings.append(
            {
                "booking_id": f"BKG{index:09d}",
                "pnr": pnr,
                "passenger_id": passenger["passenger_id"],
                "booking_date": booking_date.isoformat(),
                "booking_status": booking_status,
                "total_amount": float(amount),
                "currency": fare["currency"],
                "payment_status": payment_status,
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(bookings, output, ensure_ascii=True, indent=2)
        output.write("\n")

    print(f"Generated {len(bookings):,} bookings at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()