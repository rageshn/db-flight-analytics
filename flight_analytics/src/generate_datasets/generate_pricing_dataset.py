import csv
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from faker import Faker


ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ROOT / "datasets" / "airlines.csv"
OUTPUT_PATH = ROOT / "datasets" / "flight_pricing.csv"
CENT = Decimal("0.01")
TAX_RATE = Decimal("0.12")
FARE_CLASSES = {
    "Y": ("Economy", Decimal("55.00")),
    "J": ("Business", Decimal("155.00")),
    "F": ("First", Decimal("285.00")),
}


def main() -> None:
    faker = Faker()
    faker.seed_instance(20260926)

    with SOURCE_PATH.open("r", newline="", encoding="utf-8-sig") as source_file:
        flights = csv.DictReader(source_file)
        fieldnames = [
            "flight_number",
            "airline_code",
            "origin_airport_code",
            "destination_airport_code",
            "departure_utc",
            "arrival_utc",
            "fare_class_code",
            "fare_class",
            "configured_seats",
            "currency",
            "base_fare",
            "tax_rate_percent",
            "taxes",
            "total_cost",
        ]

        with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()

            for flight in flights:
                departure = datetime.fromisoformat(
                    flight["departure_utc"].replace("Z", "+00:00")
                )
                arrival = datetime.fromisoformat(
                    flight["arrival_utc"].replace("Z", "+00:00")
                )
                duration_hours = Decimal(
                    str((arrival - departure).total_seconds())
                ) / Decimal("3600")
                if duration_hours <= 0:
                    raise ValueError(
                        f"Non-positive flight duration: {flight['flight_number']}"
                    )

                class_seats = {
                    class_code: int(flight[field])
                    for class_code, field in (
                        ("Y", "economy_seats"),
                        ("J", "business_seats"),
                        ("F", "first_class_seats"),
                    )
                    if int(flight[field]) > 0
                }
                for class_code in sorted(
                    class_seats, key=lambda code: FARE_CLASSES[code][1]
                ):
                    class_name, hourly_rate = FARE_CLASSES[class_code]
                    adjustment = Decimal(faker.random_int(8500, 12000)) / Decimal(
                        "10000"
                    )
                    base_fare = (duration_hours * hourly_rate * adjustment).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    )
                    taxes = (base_fare * TAX_RATE).quantize(
                        CENT, rounding=ROUND_HALF_UP
                    )
                    writer.writerow(
                        {
                            "flight_number": flight["flight_number"],
                            "airline_code": flight["airline_code"],
                            "origin_airport_code": flight["origin_airport_code"],
                            "destination_airport_code": flight[
                                "destination_airport_code"
                            ],
                            "departure_utc": flight["departure_utc"],
                            "arrival_utc": flight["arrival_utc"],
                            "fare_class_code": class_code,
                            "fare_class": class_name,
                            "configured_seats": class_seats[class_code],
                            "currency": "USD",
                            "base_fare": f"{base_fare:.2f}",
                            "tax_rate_percent": "12.00",
                            "taxes": f"{taxes:.2f}",
                            "total_cost": f"{base_fare + taxes:.2f}",
                        }
                    )


if __name__ == "__main__":
    main()