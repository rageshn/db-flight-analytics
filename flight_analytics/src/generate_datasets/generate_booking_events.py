import csv
import json
import os
import random
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASETS = ROOT / "datasets"
BOOKINGS_PATH = DATASETS / "bookings.json"
BOOKING_FLIGHTS_PATH = DATASETS / "bookings_flight.json"
FLIGHTS_PATH = DATASETS / "airlines.csv"
OUTPUT_PATH = DATASETS / "booking_events.json"
SEED = 20260926


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def write_json_atomically(data: list[dict[str, object]]) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        dir=OUTPUT_PATH.parent, prefix="booking_events_", suffix=".json"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(data, output, ensure_ascii=True, indent=2)
            output.write("\n")
        os.replace(temp_name, OUTPUT_PATH)
    except Exception:
        if os.path.exists(temp_name):
            os.remove(temp_name)
        raise


def main() -> None:
    rng = random.Random(SEED)
    with BOOKINGS_PATH.open("r", encoding="utf-8-sig") as source:
        bookings = json.load(source)

    booking_flights = {
        row["booking_id"]: row for row in json.loads(BOOKING_FLIGHTS_PATH.read_text(encoding="utf-8-sig"))
    }
    flights = {
        f"FLT-{row['flight_number']}-{row['departure_utc'][:10].replace('-', '')}": row
        for row in read_csv(FLIGHTS_PATH)
    }

    events: list[dict[str, object]] = []
    for booking in bookings:
        booking_id = booking["booking_id"]
        booking_flight = booking_flights.get(booking_id)
        if booking_flight is None:
            raise ValueError(f"No booking-flight reference for {booking_id}")
        if booking_flight["passenger_id"] != booking["passenger_id"]:
            raise ValueError(f"Passenger mismatch for {booking_id}")

        flight_id = booking_flight["flight_id"]
        flight = flights.get(flight_id)
        if flight is None or flight["flight_number"] != flight_id.split("-")[1]:
            raise ValueError(f"Invalid flight reference for {booking_id}: {flight_id}")

        booking_date = date.fromisoformat(booking["booking_date"])
        departure = datetime.fromisoformat(
            flight["departure_utc"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        if booking_date > departure.date():
            raise ValueError(f"Booking {booking_id} is after its flight departure")

        day_start = datetime.combine(booking_date, time.min, tzinfo=timezone.utc)
        latest_creation = min(
            day_start + timedelta(days=1, seconds=-1),
            departure - timedelta(minutes=2),
        )
        creation_window_seconds = int((latest_creation - day_start).total_seconds())
        if creation_window_seconds < 0:
            raise ValueError(f"No valid creation time before departure for {booking_id}")
        created_at = day_start + timedelta(seconds=rng.randint(0, creation_window_seconds))
        max_transition_seconds = min(
            3600, int((departure - created_at).total_seconds()) - 1
        )
        if max_transition_seconds < 1:
            raise ValueError(f"No valid status transition time for {booking_id}")
        changed_at = created_at + timedelta(seconds=rng.randint(1, max_transition_seconds))

        event_context = {
            "booking_id": booking_id,
            "booking_flight_id": booking_flight["booking_flight_id"],
            "flight_id": flight_id,
            "passenger_id": booking["passenger_id"],
            "pnr": booking["pnr"],
        }
        events.append(
            {
                "event_type": "BOOKING_CREATED",
                **event_context,
                "old_status": None,
                "new_status": "PENDING",
                "event_time": created_at.isoformat().replace("+00:00", "Z"),
            }
        )

        status = booking["booking_status"]
        if status == "Confirmed":
            terminal_type = "BOOKING_CONFIRMED"
        elif status == "Cancelled":
            terminal_type = "BOOKING_CANCELLED"
        elif status == "Pending":
            terminal_type = rng.choice(
                ("BOOKING_CONFIRMED", "BOOKING_CANCELLED")
            )
        else:
            raise ValueError(f"Unsupported booking status for {booking_id}: {status}")

        terminal_status = (
            "CONFIRMED" if terminal_type == "BOOKING_CONFIRMED" else "CANCELLED"
        )
        events.append(
            {
                "event_type": terminal_type,
                **event_context,
                "old_status": "PENDING",
                "new_status": terminal_status,
                "event_time": changed_at.isoformat().replace("+00:00", "Z"),
            }
        )

    if len(events) != 2 * len(bookings):
        raise ValueError("Each booking must produce exactly two events")

    events.sort(
        key=lambda event: (
            datetime.fromisoformat(event["event_time"].replace("Z", "+00:00")),
            event["booking_id"],
        )
    )
    write_json_atomically(events)
    print(f"Generated {len(events):,} booking events at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()