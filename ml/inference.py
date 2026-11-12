"""Framework-independent inference using the shipped fitted model artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import joblib
import pandas as pd

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = PACKAGE_DIR / "artifacts" / "CarPredictionModel.pkl"
DEFAULT_PREPROCESSOR_PATH = PACKAGE_DIR / "artifacts" / "CarPreprocessor.pkl"
CONTRACT_PATH = PACKAGE_DIR / "feature_contract.json"

with CONTRACT_PATH.open(encoding="utf-8") as contract_file:
    FEATURE_CONTRACT = json.load(contract_file)

INPUT_FEATURES = [feature["name"] for feature in FEATURE_CONTRACT["input_features"]]
FEATURES_BY_NAME = {feature["name"]: feature for feature in FEATURE_CONTRACT["input_features"]}
RARE_COLORS = set(FEATURES_BY_NAME["color"]["rare_training_values_mapped_to_other"])


class InferenceError(ValueError):
    """Raised when raw input cannot be safely passed to the trained estimator."""


class CarPricePredictor:
    """Loads a trusted fitted preprocessor and estimator and predicts car prices."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        preprocessor_path: Path = DEFAULT_PREPROCESSOR_PATH,
    ) -> None:
        model_path = Path(model_path)
        preprocessor_path = Path(preprocessor_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"Trained model artifact not found: {model_path}")
        if not preprocessor_path.is_file():
            raise FileNotFoundError(f"Fitted preprocessor artifact not found: {preprocessor_path}")

        # Only load trusted, repository-controlled joblib files.
        self.model = joblib.load(model_path)
        self.preprocessor = joblib.load(preprocessor_path)

        transformed_features = self.preprocessor.get_feature_names_out()
        expected_count = FEATURE_CONTRACT["transformed_feature_count"]
        expected_names = FEATURE_CONTRACT["transformed_feature_names"]
        if list(transformed_features) != expected_names:
            raise ValueError(
                "The saved preprocessor's transformed feature names or ordering do not match "
                "the verified training contract."
            )
        if len(transformed_features) != expected_count:
            raise ValueError(f"Preprocessor has an unexpected number of features (expected {expected_count}).")
        if getattr(self.model, "n_features_in_", None) != expected_count:
            raise ValueError(
                "Model and fitted preprocessor are incompatible with the verified input contract."
            )

        digest = hashlib.sha256()
        digest.update(model_path.read_bytes())
        digest.update(preprocessor_path.read_bytes())
        self.model_version = digest.hexdigest()[:16]

    @staticmethod
    def validate_input(features: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(features, Mapping):
            raise InferenceError("Input must be an object containing supported car features.")
        expected = set(INPUT_FEATURES)
        supplied = set(features)
        missing = expected - supplied
        extra = supplied - expected
        if missing:
            raise InferenceError(f"Missing required feature(s): {', '.join(sorted(missing))}.")
        if extra:
            raise InferenceError(f"Unsupported feature(s): {', '.join(sorted(extra))}.")

        validated = dict(features)
        for name in ("year", "mileage"):
            value = validated[name]
            constraint = FEATURES_BY_NAME[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise InferenceError(f"{name} must be an integer.")
            if not constraint["minimum"] <= value <= constraint["maximum"]:
                raise InferenceError(
                    f"{name} must be between {constraint['minimum']} and {constraint['maximum']} "
                    "to remain within the observed training-data range."
                )

        for name in ("trim", "transmission", "body_status", "color"):
            value = validated[name]
            if not isinstance(value, str):
                raise InferenceError(f"{name} must be a string.")
            supported = FEATURES_BY_NAME[name]["supported_values"]
            if value not in supported:
                raise InferenceError(f"Unsupported {name} value.")

        return validated

    def predict(self, features: Mapping[str, Any]) -> dict[str, Any]:
        validated = self.validate_input(features)
        model_input = dict(validated)
        if model_input["color"] in RARE_COLORS:
            model_input["color"] = "Other"
        raw_frame = pd.DataFrame(
            [{name: model_input[name] for name in INPUT_FEATURES}],
            columns=INPUT_FEATURES,
        )
        transformed = self.preprocessor.transform(raw_frame)
        if transformed.shape[1] != self.model.n_features_in_:
            raise RuntimeError("Preprocessor output shape does not match the trained estimator.")
        prediction = float(self.model.predict(transformed)[0])
        return {
            "predicted_price": prediction,
            "prediction_unit": FEATURE_CONTRACT["target"]["unit_note"],
            "model_version": self.model_version,
            "input_data": validated,
        }
