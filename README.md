# Peugeot 206 Price Prediction Platform

This repository contains a trained machine-learning model and a web application for estimating the source `price` field of Peugeot 206 listings. The platform includes a React/TypeScript frontend, a FastAPI backend, PostgreSQL persistence, and an isolated ML inference package.

The estimate uses the model's original price units. **The source data does not document a currency denomination**, so the application does not label predictions as IRR, toman, or another currency. Predictions are estimates from historical listing data, not appraisals or guarantees.

## What the application does

- Accepts only the six raw features established by the training data: `year`, `mileage`, `trim`, `transmission`, `body_status`, and `color`.
- Validates the input against the observed training bounds and supported categorical values.
- Applies the saved, fitted `ColumnTransformer` once, then calls the saved Linear Regression estimator.
- Supports account registration and login, user-scoped prediction history, comparison, and conversation notes.
- Offers an assistant response only when an explicitly configured provider is available; it does not invent responses when none is configured.

The model was trained on 764 Peugeot 206 listings. This small, historical dataset does not establish current-market accuracy or applicability to other vehicles. The year and mileage limits are observed data bounds; their calendar system and distance unit are not specified.

## Architecture

```text
CarEstimation/
├── backend/
│   ├── app/                 # FastAPI routes, schemas, auth, persistence, services
│   ├── migrations/          # Alembic database migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/                 # React + TypeScript application
│   ├── Dockerfile
│   └── nginx.conf           # SPA routing and /api reverse proxy
├── ml/
│   ├── artifacts/           # Paired saved estimator and fitted preprocessor
│   ├── data/                # Source and cleaned datasets
│   ├── data_cleaning/
│   ├── data_collection/
│   ├── training/
│   ├── tests/
│   ├── feature_contract.json
│   └── inference.py         # Framework-independent inference entry point
├── docs/
│   ├── PROJECT_ANALYSIS.md
│   └── IMPLEMENTATION_PLAN.md
├── .env.example
├── docker-compose.yml
└── README.md
```

### Prediction flow

`frontend -> nginx -> FastAPI -> ml.inference.CarPricePredictor -> saved preprocessor -> saved estimator`

The model and preprocessor are separate trusted joblib artifacts under `ml/artifacts/`. The inference package checks their transformed feature names and dimensions at load time, preserves the raw input contract, and never fits or refits an artifact during a request. The final model predicts `price` directly, with no target transform or inverse transform.

## AI project context

### Frontend and UI/UX

The frontend is a React 19 and TypeScript application built with Vite. It uses React Router for page navigation, TanStack Query for API data, React Hook Form and Zod for forms and validation, Recharts for prediction history, and Lucide icons. Most of the current UI styling lives in `frontend/src/App.css`; global styles, typography, focus treatment, and color tokens are in `frontend/src/index.css`. Routes and page components are primarily in `frontend/src/App.tsx`.

The public experience includes a landing page (`/`), a model-information page (`/model`), and sign-in/registration pages (`/login`, `/register`). The authenticated workspace has a shared desktop sidebar/top bar and a collapsible mobile navigation drawer, with dashboard (`/dashboard`), new prediction (`/predict`), history (`/predictions/history`), comparison (`/compare`), profile (`/profile`), and a conversation section (`/chat`). Chat is currently presented as unavailable/coming soon; the interface should not imply that an AI assistant is connected.

The visual direction is premium, clean automotive UI: warm ivory backgrounds, off-white surfaces, charcoal text, deep forest-green actions, and a restrained bronze accent. Reuse the semantic CSS variables in `frontend/src/index.css`, keep typography readable for English and Persian, and preserve clear active, hover, keyboard-focus, loading, error, and empty states. Layouts should adapt without clipping or horizontal overflow at phone widths. Keep the local, attributed Peugeot 206 WebP photo on the model-information page; the landing page and login page currently use typographic graphics rather than car photography.

Price estimation is the application's primary task. Keep the prediction visually prominent, with its horizontal MAE-based reference range directly below the estimated value. The frontend currently uses an MAE reference of 116,716,294 and labels the range as Toman, but the source price denomination is undocumented; do not imply that the backend verifies the currency or that the range guarantees an outcome. Preserve existing prediction behavior and clearly state the model's Peugeot 206 scope and estimate limitations.

When asking an AI assistant for frontend work, ask it to inspect the relevant components and tests first, make focused changes, preserve existing features/API behavior, check responsive and accessible behavior, and run the relevant frontend tests, lint, and build. The more detailed screen-by-screen design context and a copy/paste prompt template are in [docs/PROJECT_CONTEXT_FOR_AI.md](docs/PROJECT_CONTEXT_FOR_AI.md).

## Run with Docker Compose

Requirements: Docker Engine/Desktop with the Docker Compose plugin.

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open `http://localhost:3000`. The API is available at `http://localhost:8000`; OpenAPI docs are at `http://localhost:8000/docs`. Compose starts PostgreSQL, waits for its health check, applies Alembic migrations, then starts the API and frontend. PostgreSQL data is kept in the named `postgres_data` volume.

Set strong, unique values in `.env` before deployment, especially `JWT_SECRET_KEY` and `POSTGRES_PASSWORD`. The checked-in `.env.example` values are for local development only. Production deployments also need HTTPS termination, appropriate CORS origins, and secret management outside the repository. The model artifacts are included in the backend image; rebuild it after changing them.

Useful commands:

```powershell
docker compose logs -f backend
docker compose down
```

`docker compose down -v` also deletes the PostgreSQL data volume.

## Run locally without Docker

Requirements: Python compatible with the pinned packages, Node.js 24+, and PostgreSQL (or SQLite for local backend development).

Create a Python environment and install backend/ML dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

For a local SQLite database, open PowerShell at the repository root and start the backend:

```powershell
$env:DATABASE_URL = "sqlite:///./backend.db"
$env:JWT_SECRET_KEY = "local-development-only-change-this"
$env:PYTHONPATH = "$PWD;$PWD\backend"
python -m alembic -c backend\alembic.ini upgrade head
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). Vite proxies `/api` requests to `http://localhost:8000`.

## API overview

- `GET /api/v1/health` — API and database health.
- `GET /api/v1/model/info` — model and target metadata.
- `GET /api/v1/model/features` — raw input feature contract for the form.
- `POST /api/v1/predict` — validate and save a prediction for the signed-in user.
- `/api/v1/predictions/*` — prediction history, details, and deletion for the signed-in user.
- `/api/v1/auth/*`, `/api/v1/users/*`, `/api/v1/predictions/*`, and `/api/v1/conversations/*` — authentication and user-scoped application data.

## Verified model input contract

| Feature | Type | Supported values or observed range |
|---|---|---|
| `year` | Integer | 1380–1402 (calendar system unspecified) |
| `mileage` | Integer | 0–900000 (distance unit unspecified) |
| `trim` | Category | `تیپ 1`, `تیپ 2`, `تیپ 3`, `تیپ 3 پانوراما`, `تیپ 5`, `تیپ 6` |
| `transmission` | Category | `اتوماتیک`, `دنده ای` |
| `body_status` | Category | `اتاق تعویض`, `بدون رنگ`, `خط و خش جزئی`, `درب تعویض`, `دو درب رنگ`, `دو لکه رنگ`, `دور رنگ`, `صافکاری بدون رنگ`, `چند لکه رنگ`, `کامل رنگ`, `کاپوت تعویض`, `کاپوت رنگ`, `گلگیر تعویض`, `گلگیر رنگ`, `یک درب رنگ`, `یک لکه رنگ` |
| `color` | Category | Values from the verified training contract, including rare observed colors that are grouped to `Other` before transform |

`model` and `modified_date` exist in the source dataset but are not estimator inputs. The API does not expose the model's one-hot encoded columns as user input. See `ml/feature_contract.json` and `docs/PROJECT_ANALYSIS.md` for the complete category list, observed ranges, transformed feature order, and audit details.

## Training, evaluation, and inference

The existing training code and source data are kept under `ml/`; the web API does not retrain the model. To train and evaluate locally, install the ML requirements and run from the repository root:

```powershell
python -m pip install -r ml\requirements.txt
python ml\training\train_model.py
```

Training writes the paired artifacts to `ml/artifacts/CarPredictionModel.pkl` and `ml/artifacts/CarPreprocessor.pkl`. Do not replace only one artifact: they are a matched estimator/preprocessor pair. For an inference-only example, import `CarPricePredictor` from `ml.inference` and pass a mapping containing exactly the six supported raw features.

## Evaluation information and limitations

The project owner previously reported these test metrics: MAE 116,716,294; MSE 2.28394 × 10^16; RMSE 151,127,104; R-squared 0.8945; and an approximate MAE-based score of 91.04%. They are historical, user-reported figures, not independently reproduced results for the current saved artifacts. The approximate score is a project-specific MAE calculation, not standard regression accuracy. No confidence score or prediction interval is produced.

Other limitations:

- Training data contains 764 listings and does not establish model quality for present-day listings or unsupported vehicles.
- The source price's currency is unknown.
- Year calendar system and mileage unit are not declared.
- Supported values and numeric bounds are based on the training data; rare categories may have very few examples.
- `joblib` artifacts can execute code when loaded. Only use trusted artifacts from this repository or another verified source.

## Tests and checks

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q ml\tests
.\.venv\Scripts\python.exe -m pytest -q backend\tests
Set-Location frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

The backend tests use SQLite and the real saved ML artifacts. They do not require a running PostgreSQL server. Docker image builds and the full Compose stack require a working Docker daemon.

## Data and artifact policy

The repository retains the ML training datasets and paired model artifacts to support auditability and reproducibility. Do not add credentials, `.env` files, private user data, or secrets to Git. The Docker build context excludes training datasets and includes only the artifacts and ML files needed for serving. Version model and preprocessor artifacts together, and document their training data and environment when replacing them.
