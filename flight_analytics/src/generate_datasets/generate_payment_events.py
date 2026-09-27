import csv
import json
import os
import random
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PAYMENTS_PATH = ROOT / "datasets" / "payments.csv"
OUTPUT_PATH = ROOT / "datasets" / "payment_events.json"
SEED = 20260926


def write_json_atomically(data: list[dict[str, object]]) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        dir=OUTPUT_PATH.parent, prefix="payment_events_", suffix=".json"
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
    with PAYMENTS_PATH.open("r", newline="", encoding="utf-8-sig") as source:
        payments = list(csv.DictReader(source))

    payment_bookings: dict[str, str] = {}
    events: list[dict[str, object]] = []
    for payment in payments:
        payment_id = payment["payment_id"]
        booking_id = payment["booking_id"]
        existing_booking_id = payment_bookings.setdefault(payment_id, booking_id)
        if existing_booking_id != booking_id:
            raise ValueError(f"Payment {payment_id} maps to more than one booking")

        transaction_time = datetime.fromisoformat(
            payment["transaction_time"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        payment_status = payment["payment_status"]
        if payment_status in {"Paid", "Refunded"}:
            terminal_type = "PAYMENT_SUCCESS"
        elif payment_status == "Failed":
            terminal_type = "PAYMENT_FAILED"
        elif payment_status == "Pending":
            terminal_type = rng.choice(("PAYMENT_SUCCESS", "PAYMENT_FAILED"))
        else:
            raise ValueError(f"Unsupported payment status: {payment_status}")

        event_context = {
            "payment_id": payment_id,
            "booking_id": booking_id,
            "payment_reference": payment["payment_reference"],
            "payment_method": payment["payment_method"],
            "payment_amount": float(payment["payment_amount"]),
            "currency": payment["currency"],
        }
        events.append(
            {
                "event_type": "PAYMENT_INITIATED",
                **event_context,
                "old_status": None,
                "new_status": "INITIATED",
                "event_time": transaction_time.isoformat().replace("+00:00", "Z"),
            }
        )
        completed_at = transaction_time + timedelta(seconds=rng.randint(5, 300))
        terminal_status = (
            "SUCCESS" if terminal_type == "PAYMENT_SUCCESS" else "FAILED"
        )
        events.append(
            {
                "event_type": terminal_type,
                **event_context,
                "old_status": "INITIATED",
                "new_status": terminal_status,
                "event_time": completed_at.isoformat().replace("+00:00", "Z"),
            }
        )

    if len(events) != 2 * len(payments):
        raise ValueError("Each payment must produce exactly two events")
    events.sort(
        key=lambda event: (
            datetime.fromisoformat(event["event_time"].replace("Z", "+00:00")),
            event["payment_id"],
        )
    )
    write_json_atomically(events)
    print(f"Generated {len(events):,} payment events at {OUTPUT_PATH}")


if __name__ == "__main__":
    main()