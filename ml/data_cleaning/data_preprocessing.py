
from pathlib import Path

import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "cleaned_data" / "cleaned_dataset.csv"


def preprocess_data():
    # 1. Load cleaned dataset
    df = pd.read_csv(
        DATA_PATH,
        encoding="utf-8-sig"
    )

    # 2. Select input features (X)
    X = df.drop(
        columns=["price", "model", "modified_date"]
    )

    # 3. Select target variable (y)
    y = df["price"]

    # 4. Split dataset into training and testing sets before rare-color grouping
    x_train, x_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42
    )

    # 5. Group rare colors using only the training set
    color_counts = x_train["color"].value_counts()

    rare_colors = color_counts[color_counts < 5].index

    x_train["color"] = x_train["color"].replace(rare_colors, "Other")
    x_test["color"] = x_test["color"].replace(rare_colors, "Other")

    # 6. Identify categorical features
    categorical_features = [
        "trim",
        "transmission",
        "body_status",
        "color"
    ]

    # 7. Create preprocessing transformer
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_features
            )
        ],
        remainder="passthrough"
    )

    # 8. Create a copy of the original test set before transforming it
    x_test_original = x_test.copy()

    # 9. Fit and transform training data
    x_train = preprocessor.fit_transform(x_train)

    # 10. Transform testing data
    x_test = preprocessor.transform(x_test)

    # Return results
    return x_train, x_test, y_train, y_test, preprocessor, x_test_original


def preprocess_full_data():
    # 1. Load cleaned dataset
    df = pd.read_csv(
        DATA_PATH,
        encoding="utf-8-sig"
    )

    # 2. Select input features (X)
    X = df.drop(
        columns=["price", "model", "modified_date"]
    )

    # 3. Select target variable (y)
    y = df["price"]

    # 4. Group rare colors into "Other"
    color_counts = X["color"].value_counts()

    rare_colors = color_counts[color_counts < 5].index

    X["color"] = X["color"].replace(rare_colors, "Other")

    # 5. Identify categorical features
    categorical_features = [
        "trim",
        "transmission",
        "body_status",
        "color"
    ]

    # 6. Create preprocessing transformer
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_features
            )
        ],
        remainder="passthrough"
    )

    # 7. Fit and transform the full dataset
    X = preprocessor.fit_transform(X)

    # Return results
    return X, y, preprocessor


