import csv
import json
import random
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import os
import tempfile


ROOT = Path(__file__).resolve().parent
DATASETS = ROOT / "datasets"
BOOKINGS_PATH = DATASETS / "bookings.json"
FLIGHTS_PATH = DATASETS / "airlines.csv"
PRICING_PATH = DATASETS / "flight_pricing.csv"
PASSENGERS_PATH = DATASETS / "passengers.csv"
OUTPUT_PATH = DATASETS / "bookings_flight.json"
SEED = 20260926


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def write_json_atomically(path: Path, data: object) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f"{path.stem}_", suffix=".json"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(data, output, ensure_ascii=True, indent=2)
            output.write("\n")
        os.replace(temp_name, path)
    except Exception:
        if os.path.exists(temp_name):
            os.remove(temp_name)
        raise


def main() -> None:
    rng = random.Random(SEED)
    with BOOKINGS_PATH.open("r", encoding="utf-8-sig") as source:
        bookings = json.load(source)

    flights = {
        (row["flight_number"], row["departure_utc"]): row
        for row in read_csv(FLIGHTS_PATH)
    }
    passengers = {row["passenger_id"] for row in read_csv(PASSENGERS_PATH)}
    fares_by_amount: dict[Decimal, list[dict[str, str]]] = defaultdict(list)
    fares_by_class: dict[str, list[dict[str, str]]] = defaultdict(list)
    for fare in read_csv(PRICING_PATH):
        fares_by_amount[Decimal(fare["total_cost"])].append(fare)
        fares_by_class[fare["fare_class_code"]].append(fare)

    seats_used: dict[tuple[str, str], int] = defaultdict(int)
    booking_flight_rows: list[dict[str, object]] = []
    used_seats: dict[str, set[str]] = defaultdict(set)
    adjusted_booking_totals = 0

    for booking in bookings:
        if booking["passenger_id"] not in passengers:
            raise ValueError(f"Unknown passenger: {booking['passenger_id']}")

        booking_date = date.fromisoformat(booking["booking_date"])
        matching_fares = [
            fare
            for fare in fares_by_amount[Decimal(str(booking["total_amount"]))]
            if date.fromisoformat(fare["departure_utc"][:10]) >= booking_date
        ]
        rng.shuffle(matching_fares)
        selected: tuple[dict[str, str], dict[str, str], str, str] | None = None

        def try_assign(fare: dict[str, str]) -> tuple[dict[str, str], dict[str, str], str, str] | None:
            flight_key = (fare["flight_number"], fare["departure_utc"])
            flight = flights.get(flight_key)
            if flight is None:
                return None
            fare_class_code = fare["fare_class_code"]
            class_capacity = int(fare["configured_seats"])
            flight_id = (
                f"FLT-{fare['flight_number']}-"
                f"{fare['departure_utc'][:10].replace('-', '')}"
            )
            seat_key = (flight_id, fare_class_code)
            if seats_used[seat_key] >= class_capacity:
                return None

            seats_used[seat_key] += 1
            seat_number = f"{fare_class_code}{seats_used[seat_key]:03d}"
            if seat_number in used_seats[flight_id]:
                raise ValueError(f"Duplicate seat {seat_number} on {flight_id}")
            used_seats[flight_id].add(seat_number)
            return fare, flight, flight_id, seat_number

        for fare in matching_fares:
            selected = try_assign(fare)
            if selected is not None:
                break

        if selected is None and matching_fares:
            fallback_class = matching_fares[0]["fare_class_code"]
            fallback_fares = [
                fare
                for fare in fares_by_class[fallback_class]
                if date.fromisoformat(fare["departure_utc"][:10]) >= booking_date
            ]
            rng.shuffle(fallback_fares)
            for fare in fallback_fares:
                selected = try_assign(fare)
                if selected is not None:
                    booking["total_amount"] = float(Decimal(fare["total_cost"]))
                    adjusted_booking_totals += 1
                    break

        if selected is None:
            raise ValueError(
                f"No eligible unoccupied fare seat found for booking {booking['booking_id']}"
            )

        fare, _flight, flight_id, seat_number = selected
        booking_flight_rows.append(
            {
                "booking_flight_id": f"BF{len(booking_flight_rows) + 1:09d}",
                "booking_id": booking["booking_id"],
                "flight_id": flight_id,
                "passenger_id": booking["passenger_id"],
                "seat_number": seat_number,
                "cabin_class": fare["fare_class"],
                "fare_class": fare["fare_class_code"],
                "base_fare": float(Decimal(fare["base_fare"])),
                "taxes": float(Decimal(fare["taxes"])),
                "total_fare": float(Decimal(fare["total_cost"])),
                "booking_status": booking["booking_status"],
            }
        )

    write_json_atomically(OUTPUT_PATH, booking_flight_rows)
    if adjusted_booking_totals:
        write_json_atomically(BOOKINGS_PATH, bookings)
    print(
        f"Generated {len(booking_flight_rows):,} booking-flight rows at {OUTPUT_PATH}; "
        f"synchronized {adjusted_booking_totals} parent booking totals."
    )


if __name__ == "__main__":
    main()