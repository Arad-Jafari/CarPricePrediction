
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

df = pd.read_csv(DATA_DIR / "raw_data" / "raw_cars_dataset.csv", encoding="utf-8-sig")

# Convert year to numeric
df["year"] = pd.to_numeric(df["year"], errors="coerce")

# Convert mileage to numeric
df["mileage"] = df["mileage"].replace(
    "صفر کیلومتر", "0"
)
df["mileage"] = (
    df["mileage"]
    .astype(str)
    .str.replace(",", "", regex=False)
    .str.extract(r"(\d+)", expand=False)
)

df["mileage"] = pd.to_numeric(df["mileage"], errors="coerce")

# Convert price to numeric
df["price"] = (
    df["price"]
    .astype(str)
    .str.replace(",", "", regex=False)
)

df["price"] = pd.to_numeric(df["price"], errors="coerce")

# Remove the extreme price anomaly
df = df[
    ~(
        (df["year"] == 1390) &
        (df["trim"] == "تیپ 6") &
        (df["mileage"] == 8000) &
        (df["price"] == 3650000000)
    )
]

# Remove repeated vehicle feature combinations

duplicate_columns = [
    "model",
    "year",
    "mileage",
    "trim",
    "transmission",
    "body_status",
    "color",
    "price"
]

# print("\n--- Duplicate Removal ---")

duplicates_before = df.duplicated(
    subset=duplicate_columns
).sum()

# print("Repeated combinations:", duplicates_before)

df = df.drop_duplicates(
    subset=duplicate_columns,
    keep="first"
)

print("Df len", len(df))



# Save a new dataset
(DATA_DIR / "cleaned_data").mkdir(parents=True, exist_ok=True)
df.to_csv(DATA_DIR / "cleaned_data" / "cleaned_dataset.csv", index=False, encoding="utf-8-sig")
