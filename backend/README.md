# Peugeot 206 backend

FastAPI service backed by SQLAlchemy 2 and PostgreSQL. Prediction requests call
the repository's `ml.inference.CarPricePredictor`; the API does not reproduce
preprocessing or accept a model name. Price responses retain the source price
units and do not assign a currency.

## Setup

From the repository root, create a Python environment, install
`backend/requirements.txt`, and set the variables in `backend/.env.example` in
your process environment. No `.env` file or signing secret is committed.
Production must set a random `JWT_SECRET_KEY` of at least 32 characters,
`ENVIRONMENT=production`, and a PostgreSQL `DATABASE_URL` (or all `POSTGRES_*`
values shown in `.env.example`). The `POSTGRES_HOST` default matches a Compose
database service named `db`. Refresh cookies are Secure in production and always
HttpOnly, SameSite=Lax; refresh and logout also require the `csrf_token` cookie
value in the `X-CSRF-Token` header.

The backend's exact configuration variable names are `ENVIRONMENT`,
`DATABASE_URL`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`,
`ACCESS_TOKEN_MINUTES`, `REFRESH_TOKEN_DAYS`, `MODEL_PATH`,
`PREPROCESSOR_PATH`, `CORS_ORIGINS`, and `CHAT_PROVIDER`. `JWT_ALGORITHM`
defaults to `HS256`; only `HS256`, `HS384`, and `HS512` are accepted, and
production signing keys must meet the selected algorithm's minimum byte length.
`MODEL_PATH` and `PREPROCESSOR_PATH` default to the artifacts bundled with
`ml.inference`; set them in Compose only when mounting artifacts elsewhere.

From the repository root, apply migrations and run the service:

```powershell
python -m alembic -c backend/alembic.ini upgrade head
uvicorn app.main:app --app-dir backend
```

`DATABASE_URL` should use `postgresql+psycopg://...` in production. For local
development the default is SQLite; PostgreSQL stores prediction input as JSONB.
For test isolation, tests use in-memory SQLite.
Alembic migrations add active-user status and optional message metadata, and
store prediction prices with a fixed-precision numeric database type.

All prediction, history, and conversation endpoints require a bearer access
token. No AI response provider is configured by default. Chat message submission
still persists the user's note and returns `{items: [user_message],
assistant_response_available: false}`; it does not fabricate an assistant
response. When `CHAT_PROVIDER` names a configured dotted Python class
implementing `generate_reply(messages)`, a real response is generated and both
messages are persisted and returned with `assistant_response_available: true`.
If that configured provider fails, the request returns an error and does not
store either message. Conversation/message retrieval and title editing work
regardless.

Frontend-facing routes are available both without a prefix (`/auth`, `/users`,
`/predictions`, `/conversations`) and under `/api`. Registration accepts
`full_name`, `email`, `password`, and `password_confirmation`, returning a
`{id, full_name, email}` user. Login returns `{access_token, token_type,
user}`; refresh returns `{access_token, token_type}` and rotates the refresh
cookie. `POST /api/v1/users/me/password` accepts
`{current_password,new_password,password_confirmation}`, verifies the current
password, requires a confirmed password of at least 12 characters, and revokes
refresh sessions after a successful change. Prediction history is
`{items, total, page, page_size}`. Conversation
lists, details, and message collections use `{items: [...]}`; message
submission accepts `{content}` and returns stored messages only when a
configured provider supplied an actual assistant response. Without one, the
user message is still stored and returned alone; clients should not display an
AI reply. Conversation titles can be edited with authenticated
`PATCH /api/v1/conversations/{conversation_id}`. Conversation list responses
include `total`, counting the current user's conversations after search filters
and before pagination. `DELETE /api/v1/predictions` clears only the authenticated user's
prediction history. Feature metadata is returned as `{features: [...], target:
{...}}`; each feature follows `ml/feature_contract.json`, and target metadata
preserves the source price-unit note without asserting a currency.

## Validation

From `backend/`, run:

```powershell
python -m pytest
```

Health, model metadata, and the supported feature contract are available at
`/api/v1/health`, `/api/v1/model/info`, and `/api/v1/model/features`. Model
artifacts are initialized in the FastAPI lifespan on startup with the configured
paths; tests may inject a predictor to avoid loading them. Model info includes
`chat_assistant_available`, which is true only when the configured real provider
has loaded; otherwise chat accepts savable user notes without an AI response.
