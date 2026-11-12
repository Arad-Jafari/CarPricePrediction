# Verified Project Analysis

## Audit status

This analysis reflects the repository as inspected on 2026-11-12, before application restructuring. There was no FastAPI backend, React frontend, prediction API, deployment configuration, database, migration setup, test suite, or conversational model/provider in the repository. The repository consisted of the Python data collection and ML scripts, CSV/JSON datasets, two scikit-learn pickle artifacts, and the root README and requirements file.

## Existing ML workflow

1. `BamaApiEndpintData/bama_raw_data.py` requests advertisements from Bama's search API and writes JSON to `BamaApiEndpintData/raw_data/cars.json`.
2. `BamaApiEndpintData/bama_extracted_data.py` extracts listing fields and writes `data/raw_data/raw_cars_dataset.csv`.
3. `data_cleaning/data_cleaning.py` normalizes numeric year, mileage, and price, removes a specific price anomaly and exact duplicates, then writes `data/cleaned_data/cleaned_dataset.csv`.
4. `data_cleaning/data_preprocessing.py` creates an 80/20 split for evaluation; groups rare colors based on training data; one-hot encodes `trim`, `transmission`, `body_status`, and `color`; and passes other retained columns through. `preprocess_full_data()` applies the same feature selection and rare-color grouping to all rows for the final model.
5. `model/train_model.py` trains and evaluates `sklearn.linear_model.LinearRegression`, then writes the final model and preprocessor to `model/trained_model/CarPredictionModel.pkl` and `model/trained_model/CarPreprocessor.pkl`.

The scripts use working-directory-relative paths. For example, preprocessing reads `../data/cleaned_data/cleaned_dataset.csv`, and the Bama scripts expect to be run from their own directory. Moving the code requires repairing these paths or running from the expected directory.

## Verified inference contract

| Property | Verified finding |
|---|---|
| Prediction target | `price` (regression; not a category) |
| Target transformation | None; training fits directly against the `price` column |
| Target units | Unspecified by code and dataset metadata. Values are preserved from the Bama `price.price` field. Do not label as IRR or toman without confirmation. |
| Dataset | 764 rows, 9 columns; all rows have `model == 206` |
| Model artifact | `sklearn.linear_model.LinearRegression`, `n_features_in_ == 39`, 801 bytes |
| Preprocessor artifact | `sklearn.compose.ColumnTransformer`, 3,517 bytes |
| Saved estimator includes preprocessing | No. The estimator accepts the 39-column transformed matrix; apply the separate fitted preprocessor exactly once. |
| Saved artifact library version | Successfully loaded with scikit-learn 1.9.1. The repository requirements pin scikit-learn 1.9.1. |
| Fitted transformed shape | 39 columns; feature names are available from the `ColumnTransformer`. |
| Baseline inference | Transforming the first cleaned-data row with the saved preprocessor and model produced `1319399548.4906769` before restructuring. This is a parity reference only, not a user-facing sample valuation. |

### Raw training input

The input DataFrame is created by dropping `price`, `model`, and `modified_date` from the cleaned dataset. Its exact raw feature order is:

1. `year` — integer in the observed training data, range 1380–1402.
2. `mileage` — integer in the observed training data, range 0–900000.
3. `trim` — categorical string.
4. `transmission` — categorical string.
5. `body_status` — categorical string.
6. `color` — categorical string.

All six fields are supplied by the listing data; the model identifier `model` is present in the dataset but dropped from model inputs. The collection script identifies Peugeot 206 listings by URL and the cleaned dataset has only the integer model value `206`. The model therefore has evidence only for Peugeot 206 listings; its output does not establish support for other Peugeot variants or vehicles.

### Fitted categories and rare colors

`OneHotEncoder(handle_unknown="ignore")` is fitted for `trim`, `transmission`, `body_status`, and `color`. The fitted encoder categories are authoritative for categories that have encoded columns:

- `trim`: `تیپ 1`, `تیپ 2`, `تیپ 3`, `تیپ 3 پانوراما`, `تیپ 5`, `تیپ 6`
- `transmission`: `اتوماتیک`, `دنده ای`
- `body_status`: `اتاق تعویض`, `بدون رنگ`, `خط و خش جزئی`, `درب تعویض`, `دو درب رنگ`, `دو لکه رنگ`, `دور رنگ`, `صافکاری بدون رنگ`, `چند لکه رنگ`, `کامل رنگ`, `کاپوت تعویض`, `کاپوت رنگ`, `گلگیر تعویض`, `گلگیر رنگ`, `یک درب رنگ`, `یک لکه رنگ`
- `color`: `Other`, `آبی`, `بادمجانی`, `بژ`, `خاکستری`, `سفید`, `قرمز`, `قهوه ای`, `مشکی`, `نقره ای`, `نوک مدادی`, `گیلاسی`, `یشمی`

During final training, raw colors occurring fewer than five times are replaced by `Other` before fitting. The fitted preprocessor alone does not retain the mapping from individual rare raw colors to `Other`; `OneHotEncoder` ignores an unrecognized category. Inference must therefore define and document a safe color policy rather than silently pretending the saved preprocessor performs rare-color grouping. The API should reject unverified categorical values unless an explicit training-compatible mapping is established.

Year and mileage observed extrema are dataset facts, not proven valid physical bounds. The dataset does not identify their calendar or distance unit explicitly. API metadata should make this limitation clear.

## Artifact identity and baseline

Before restructuring, SHA-256:

- `CarPredictionModel.pkl`: `114471bd7590fb2283fe2e153e2f70952af081dd4c8ad84c3ae34598c2b45f52`
- `CarPreprocessor.pkl`: `a9c53605f73a27c3465a4e073a5d1ea038c0d2cab5fa570f9cd29b2ac5a73ccf`

Neither artifact is a scikit-learn `Pipeline`; serialized model and preprocessor must stay paired. Do not retrain during refactoring. Pickle/joblib files must only be loaded from trusted project-controlled paths.

## Other verified scope

- `requirements.txt` pins the existing ML dependencies, including pandas 3.1.1 and scikit-learn 1.9.1.
- There is no existing `CarPreprocessor` class or symbol. “CarPreprocessor” refers to the saved `ColumnTransformer` artifact named `CarPreprocessor.pkl`.
- There is no LLM or conversational assistant implementation. A future chat provider must not claim to be model-generated or fabricate valuation explanations.
- There was no existing end-to-end inference function, API, or test. The baseline above was executed directly by loading both artifacts and applying the saved transform then estimator.
- Existing model scripts perform model training when invoked and are not an inference service.

## User-reported earlier evaluation

The project owner supplied the following previous 20%-test-set baseline results: approximate MAE-based score 91.04%, MAE 116,716,294, MSE 2.28394 × 10^16, RMSE 151,127,104, and R-squared 0.8945. These values are not stored in the repository or serialized artifacts and have not been independently reproduced in this audit. They predate the latest preprocessing changes, including train-only rare-color grouping, so they must not be presented as confirmed performance of the current artifacts. “Approximate Accuracy” is the project's custom `100 - MAE / mean(actual) * 100` score, not a standard regression accuracy metric.

## Risks and unknowns

- The currency denomination and meaning of the numeric price are not declared in the training data/code. Confirm this before presenting a currency label or conversion.
- Several rarer `body_status` categories are represented by only one or two rows, so category membership is verified but prediction quality for those categories is not.
- The raw color-to-`Other` grouping map is not serialized. The fitted encoder has an `Other` category but does not map arbitrary unseen raw values to it.
- The model is trained on one 764-row dataset and reports no persisted evaluation metrics; do not make unsupported accuracy/confidence claims.
- No baseline API/web implementation existed, so there is no previous UI/API behavior to preserve.

## Post-audit implementation and verification

The audit above records the repository before restructuring, so its original paths describe the pre-move source layout. The current implementation is separated into `ml/`, `backend/`, and `frontend/`; the saved model and preprocessor remain a paired artifact set. The current inference service loads them without fitting, and the backend exposes both the web application's history endpoint and `POST /api/v1/predict`.

Verification performed after implementation:

- ML artifact and inference tests: 4 passed.
- Backend API/auth/ownership/inference tests: 19 passed.
- Alembic upgrade to head: passed against SQLite.
- Frontend tests: 7 passed; lint and the TypeScript/Vite production build passed.
- Live request flow through Vite's `/api` proxy: metadata, registration, login, profile, real model prediction, saved history, and conversation note all succeeded.
- `docker compose config --quiet` passed.

The Docker CLI could validate the Compose configuration, but Docker Desktop's Linux engine was unavailable, so container images and the complete Compose runtime were not built or exercised. Frontend tests run in jsdom and the live Vite/API request flow passed; real-browser automation was not run.
