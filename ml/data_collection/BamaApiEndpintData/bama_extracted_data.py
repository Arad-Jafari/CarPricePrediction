
import json
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# 1. Load JSON data
with open(Path(__file__).resolve().parent / "raw_data" / "cars.json", "r", encoding="utf-8") as file:
    cars = json.load(file)


# 2. Extract relevant features
extracted_cars = []

for car in cars:

    detail = car.get("detail") or {}
    price_data = car.get("price") or {}

    # Identify car model
    car_url = detail.get("url", "").lower()

    if "peugeot-206" in car_url:
        model = "206"
    else:
        model = None

    # Extract selected features
    extracted_car = {
        "model": model,
        "year": detail.get("year"),
        "mileage": detail.get("mileage"),
        "trim": detail.get("trim"),
        "transmission": detail.get("transmission"),
        "body_status": detail.get("body_status"),
        "color": detail.get("body_color"),
        "modified_date": detail.get("modified_date"),
        "price": price_data.get("price")
    }

    extracted_cars.append(extracted_car)


# 3. Create DataFrame
df = pd.DataFrame(extracted_cars)


# 4. Display DataFrame information
print("\nFirst 10 rows:")
print(df.head(10))

print("\nDataFrame information:")
print(df.info())

print("\nMissing values:")
print(df.isnull().sum())


# 5. Save extracted data
(DATA_DIR / "raw_data").mkdir(parents=True, exist_ok=True)
df.to_csv(DATA_DIR / "raw_data" / "raw_cars_dataset.csv", index=False, encoding="utf-8-sig")

print(f"Total advertisements extracted: {len(df)}")
