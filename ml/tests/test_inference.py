from pathlib import Path
import unittest

import pandas as pd

from ml.inference import CarPricePredictor, InferenceError, INPUT_FEATURES


class CarPricePredictorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = CarPricePredictor()

    def test_artifacts_match_verified_transformed_shape(self):
        self.assertEqual(self.predictor.model.n_features_in_, 39)
        self.assertEqual(len(self.predictor.preprocessor.get_feature_names_out()), 39)

    def test_prediction_matches_pre_refactor_baseline(self):
        dataset_path = Path(__file__).resolve().parents[1] / "data" / "cleaned_data" / "cleaned_dataset.csv"
        row = pd.read_csv(dataset_path, encoding="utf-8-sig").iloc[0]
        result = self.predictor.predict(
            {
                "year": int(row["year"]),
                "mileage": int(row["mileage"]),
                "trim": row["trim"],
                "transmission": row["transmission"],
                "body_status": row["body_status"],
                "color": row["color"],
            }
        )
        self.assertEqual(list(result["input_data"]), INPUT_FEATURES)
        self.assertAlmostEqual(result["predicted_price"], 1319399548.4906769, places=5)

    def test_rare_observed_color_is_grouped_for_inference_but_preserved_as_input(self):
        row = {
            "year": 1398,
            "mileage": 95000,
            "trim": "تیپ 2",
            "transmission": "دنده ای",
            "body_status": "بدون رنگ",
            "color": "دلفینی",
        }
        normalized = self.predictor.validate_input(row)
        self.assertEqual(normalized["color"], "دلفینی")
        prediction = self.predictor.predict(row)
        self.assertEqual(prediction["input_data"]["color"], "دلفینی")
        self.assertIsInstance(prediction["predicted_price"], float)

    def test_rejects_missing_extra_and_unknown_values(self):
        valid = {
            "year": 1398,
            "mileage": 95000,
            "trim": "تیپ 2",
            "transmission": "دنده ای",
            "body_status": "بدون رنگ",
            "color": "سفید",
        }
        with self.assertRaises(InferenceError):
            self.predictor.validate_input({key: value for key, value in valid.items() if key != "year"})
        with self.assertRaises(InferenceError):
            self.predictor.validate_input({**valid, "model": "206"})
        with self.assertRaises(InferenceError):
            self.predictor.validate_input({**valid, "trim": "unsupported"})
        with self.assertRaises(InferenceError):
            self.predictor.validate_input({**valid, "mileage": 900001})


if __name__ == "__main__":
    unittest.main()
