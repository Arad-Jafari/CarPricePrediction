
from pathlib import Path

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


# # ==================================================
# # 1. Load Dataset
# # ==================================================
#
df = pd.read_csv(
    Path(__file__).resolve().parents[1] / "data" / "cleaned_data" / "cleaned_dataset.csv",
    encoding="utf-8-sig"
)
#
# # Make sure categorical text has no extra whitespace
# categorical_columns = [
#     "trim",
#     "transmission",
#     "body_status",
#     "color"
# ]
#
# for column in categorical_columns:
#     df[column] = df[column].str.strip()
#
#
# # ==================================================
# # 2. Basic Dataset Information
# # ==================================================
#
# print("\n--- Dataset Information ---")
# print("Number of rows:", df.shape[0])
# print("Number of columns:", df.shape[1])
#
# print("\n--- Column Data Types ---")
# print(df.dtypes)
#
# print("\n--- Missing Values ---")
# print(df.isnull().sum())
#
# print("\n--- Numerical Statistics ---")
# print(df[["year", "mileage", "price"]].describe())
#
#
# # ==================================================
# # 3. Categorical Feature Analysis
# # ==================================================
#
# print("\n--- Categorical Feature Distributions ---")
#
# for column in categorical_columns:
#     print(f"\n{column.upper()}")
#     print(df[column].value_counts(dropna=False))
#
#
# # ==================================================
# # 4. Numerical Feature Visualization
# # ==================================================
#
# numerical_columns = ["year", "mileage", "price"]
#
# fig, axes = plt.subplots(1, 3, figsize=(15, 5))
#
# for ax, column in zip(axes, numerical_columns):
#     sns.histplot(
#         data=df,
#         x=column,
#         kde=True,
#         ax=ax
#     )
#
#     ax.set_title(f"{column.capitalize()} Distribution")
#
# plt.tight_layout()
# plt.show()
#
#
# # ==================================================
# # 5. Categorical Feature Visualization
# # ==================================================
#
# for column in categorical_columns:
#
#     plt.figure(figsize=(12, 5))
#
#     order = df[column].value_counts().index
#
#     sns.countplot(
#         data=df,
#         x=column,
#         order=order
#     )
#
#     plt.title(f"{column.capitalize()} Distribution")
#     plt.xticks(rotation=45, ha="right")
#     plt.tight_layout()
#     plt.show()
#
#
# # ==================================================
# # 6. Rare Category Analysis
# # ==================================================
#
# for column in ["body_status", "color"]:
#
#     counts = df[column].value_counts()
#
#     rare_categories = counts[counts < 5]
#
#     print(f"\n--- Rare Categories in {column} ---")
#     print(rare_categories)
#
#     print("Number of rare categories:", len(rare_categories))
#     print("Total records:", rare_categories.sum())
#
#
# # ==================================================
# # 7. Price Analysis by Categorical Features
# # ==================================================
#
# group_columns = [
#     "trim",
#     "transmission",
#     "body_status"
# ]
#
# for column in group_columns:
#
#     price_summary = df.groupby(column)["price"].agg(
#         ["count", "mean", "median", "min", "max"]
#     )
#
#     print(f"\n--- Price Statistics by {column} ---")
#     print(price_summary.sort_values("median").to_string())
#
#
# # ==================================================
# # 8. Correlation Analysis
# # ==================================================
#
# correlation_matrix = df[
#     ["year", "mileage", "price"]
# ].corr()
#
# print("\n--- Correlation Matrix ---")
# print(correlation_matrix)
#
#
# # ==================================================
# # 9. Correlation Heatmap
# # ==================================================
#
# plt.figure(figsize=(8, 6))
#
# sns.heatmap(
#     correlation_matrix,
#     annot=True,
#     cmap="coolwarm",
#     fmt=".2f",
#     linewidths=0.5,
#     vmin=-1,
#     vmax=1
# )
#
# plt.title("Correlation Heatmap")
# plt.tight_layout()
# plt.show()
#
#
# # ==================================================
# # 10. Numerical Outlier Visualization
# # ==================================================
#
# fig, axes = plt.subplots(1, 3, figsize=(15, 5))
#
# for ax, column in zip(axes, numerical_columns):
#
#     sns.boxplot(
#         data=df,
#         y=column,
#         ax=ax
#     )
#
#     ax.set_title(f"{column.capitalize()} Boxplot")
#
# plt.tight_layout()
# plt.show()
#

# ==================================================
# 11. Duplicate Analysis
# ==================================================

# print("\n--- Duplicate Analysis ---")
#
# print("Exact duplicate rows:", df.duplicated().sum())
#
# duplicate_columns = [
#     "model",
#     "year",
#     "mileage",
#     "trim",
#     "transmission",
#     "body_status",
#     "color",
#     "price"
# ]
#
# duplicate_combinations = df[
#     df.duplicated(
#         subset=duplicate_columns,
#         keep=False
#     )
# ].sort_values(by=duplicate_columns)
#
# print("\nDuplicate feature combinations:")
# print(duplicate_combinations.to_string(index=False))
#
# print(
#     "\nNumber of repeated feature combinations:",
#     df.duplicated(subset=duplicate_columns).sum()
# )
