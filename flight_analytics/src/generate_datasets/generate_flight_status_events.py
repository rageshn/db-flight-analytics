import csv
import json
import os
import random
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FLIGHTS_PATH = ROOT / "datasets" / "airlines.csv"
OUTPUT_PATH = ROOT / "datasets" / "flight_status_events.json"
EVENT_COUNT = 100_000
CANCELLATION_RATE = 0.05
SEED = 20260926
GATES = tuple(f"{letter}{number:02d}" for letter in "ABCDEFGH" for number in range(1, 31))


def flight_id(flight: dict[str, str]) -> str:
    departure_day = flight["departure_utc"][:10].replace("-", "")
    return f"FLT-{flight['flight_number']}-{departure_day}"


def write_json_atomically(data: list[dict[str, object]]) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        dir=OUTPUT_PATH.parent, prefix="flight_status_events_", suffix=".json"
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
    with FLIGHTS_PATH.open("r", newline="", encoding="utf-8-sig") as source:
        flights = list(csv.DictReader(source))
    if not flights:
        raise ValueError("The flight schedule is empty")

    cancelled_indices = set(
        rng.sample(range(len(flights)), round(len(flights) * CANCELLATION_RATE))
    )
    base_event_count = 3 * len(flights) - len(cancelled_indices)
    delay_event_count = EVENT_COUNT - base_event_count
    if delay_event_count < 0:
        raise ValueError("The requested count is too small for one lifecycle per flight")

    delay_counts = [0] * len(flights)
    for _ in range(delay_event_count):
        delay_counts[rng.randrange(len(flights))] += 1

    events: list[dict[str, object]] = []
    for index, flight in enumerate(flights):
        scheduled_departure = datetime.fromisoformat(
            flight["departure_utc"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        scheduled_arrival = datetime.fromisoformat(
            flight["arrival_utc"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        identifier = flight_id(flight)
        gate = rng.choice(GATES)
        delay_count = delay_counts[index]
        created_at = scheduled_departure - timedelta(
            days=rng.randint(2, 45), minutes=rng.randint(0, 1439)
        )

        events.append(
            {
                "event_type": "FLIGHT_CREATED",
                "flight_id": identifier,
                "flight_number": flight["flight_number"],
                "old_status": None,
                "new_status": "SCHEDULED",
                "delay_minutes": 0,
                "gate": gate,
                "event_time": created_at.isoformat().replace("+00:00", "Z"),
            }
        )

        total_delay_minutes = 0
        for delay_index in range(delay_count):
            previous_status = "SCHEDULED" if delay_index == 0 else "DELAYED"
            total_delay_minutes += rng.randint(5, 45)
            delayed_at = scheduled_departure - timedelta(
                hours=2 * (delay_count - delay_index)
            )
            events.append(
                {
                    "event_type": "FLIGHT_DELAYED",
                    "flight_id": identifier,
                    "flight_number": flight["flight_number"],
                    "old_status": previous_status,
                    "new_status": "DELAYED",
                    "delay_minutes": total_delay_minutes,
                    "gate": gate,
                    "event_time": delayed_at.isoformat().replace("+00:00", "Z"),
                }
            )

        if index in cancelled_indices:
            cancelled_at = scheduled_departure - timedelta(minutes=30)
            events.append(
                {
                    "event_type": "FLIGHT_CANCELLED",
                    "flight_id": identifier,
                    "flight_number": flight["flight_number"],
                    "old_status": "DELAYED" if delay_count else "SCHEDULED",
                    "new_status": "CANCELLED",
                    "delay_minutes": total_delay_minutes,
                    "gate": gate,
                    "event_time": cancelled_at.isoformat().replace("+00:00", "Z"),
                }
            )
            continue

        departed_at = scheduled_departure + timedelta(minutes=total_delay_minutes)
        events.append(
            {
                "event_type": "FLIGHT_DEPARTED",
                "flight_id": identifier,
                "flight_number": flight["flight_number"],
                "old_status": "DELAYED" if delay_count else "SCHEDULED",
                "new_status": "DEPARTED",
                "delay_minutes": total_delay_minutes,
                "gate": gate,
                "event_time": departed_at.isoformat().replace("+00:00", "Z"),
            }
        )
        landed_at = scheduled_arrival + timedelta(minutes=total_delay_minutes)
        events.append(
            {
                "event_type": "FLIGHT_LANDED",
                "flight_id": identifier,
                "flight_number": flight["flight_number"],
                "old_status": "DEPARTED",
                "new_status": "LANDED",
                "delay_minutes": total_delay_minutes,
                "gate": gate,
                "event_time": landed_at.isoformat().replace("+00:00", "Z"),
            }
        )

    if len(events) != EVENT_COUNT:
        raise ValueError(f"Generated {len(events)} events instead of {EVENT_COUNT}")

    events.sort(key=lambda event: (event["event_time"], event["flight_id"]))
    write_json_atomically(events)
    print(f"Generated {len(events):,} flight status events at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()