
import requests
from rich import print
import json
from datetime import datetime
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent / "raw_data" / "cars.json"

url = "https://bama.ir/cad/api/search"

all_cars = []

vehicles = [
    "peugeot,206ir"
]

for vehicle in vehicles:

    for page in range(35):

        params = {
            "vehicle": vehicle,
            "priceTo": 5000000000,
            "pageIndex": page
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Get advertisements from the API response
        ads = data.get("data", {}).get("ads", [])

        for ad in ads:

            # Ignore banners and other non-ad entries
            if ad.get("type") != "ad":
                continue

            detail = ad.get("detail", {})

            # Check that the listing is actually a Peugeot 207 or 206
            car_url = detail.get("url", "").lower()

            breadcrumbs = detail.get("breadcrump", {}).get("links", [])

            breadcrumb_urls = [
                link.get("url", "").lower()
                for link in breadcrumbs
            ]

            is_206 = (
                detail.get("brand") == "peugeot"
                and any(
                    "peugeot-206" in link
                    for link in [car_url] + breadcrumb_urls
                )
            )

            if is_206:
                all_cars.append(ad)

        print(
            f"[green]Vehicle: {vehicle} | Page {page + 1} fetched successfully![/green] "
            f"Total matching cars: {len(all_cars)}"
        )

from datetime import datetime

start_date = datetime.fromisoformat("2026-11-01")

filtered_cars = [
    car for car in all_cars
    if datetime.fromisoformat(
        car["detail"]["modified_date"]
    ) >= start_date
]

# Save filtered results
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(filtered_cars, f, ensure_ascii=False, indent=4)

print(f"Total Peugeot 206 cars since November 1: {len(filtered_cars)}")