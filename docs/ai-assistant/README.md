# Local AI assistant: implementation and validation guide

This note describes the current assistant implementation and gives the next
steps for validating it on a machine with a working Ollama model. It does not
claim production readiness: the backend's automated tests use fake providers,
and real Ollama generation has not succeeded in the development environment.

## Architecture

```text
React chat UI
  -> authenticated /api/v1/conversations/* routes
  -> conversation/message persistence (SQLAlchemy)
  -> prompt/context assembly and authorized application data helpers
  -> ChatProvider contract
       -> Ollama HTTP API (default local implementation)
       -> optional dotted-path custom provider
  -> backend translates Ollama NDJSON into browser SSE events
```

Conversation and prediction APIs are user-scoped. The assistant does not get
direct database access: prediction context is fetched through a backend helper
filtered by the authenticated user. Prompt instructions are not an
authorization boundary; ownership checks in the backend are.

## Request and persistence lifecycle

1. The frontend fetches `/api/v1/model/info`, displays provider availability,
   and gets the provider's configured model and installed model names.
2. The user can select an installed model and start a new conversation or
   restore/search/rename/delete an existing one.
3. The backend verifies the conversation owner and selected model, persists the
   user message, assembles the configured system prompt and a bounded history,
   and optionally adds the authenticated user's latest prediction when the
   request asks for it.
4. Ollama's newline-delimited JSON chunks are decoded and emitted as
   `start`, `token`, `done`, and `error` Server-Sent Events. The frontend
   appends each token as it arrives and supports aborting the request.
5. A completed assistant response is persisted with its model and `complete`
   status. A response interrupted after producing tokens is saved with
   `interrupted` status. Regeneration supersedes the earlier response rather
   than duplicating the user message.

Conversation message APIs require bearer authentication. Relevant endpoints:

- `GET /api/v1/model/info` — status plus installed chat models.
- `GET /api/v1/chat/models` — provider availability and model list.
- `GET /api/v1/conversations?search=...&limit=...` — current user's history
  and latest-message previews.
- `GET /api/v1/conversations/{id}/messages` — restore a conversation.
- `POST /api/v1/conversations/{id}/messages/stream` — stream a new reply.
- `POST /api/v1/conversations/{id}/messages/{message_id}/regenerate/stream` —
  regenerate an assistant reply.
- `POST /api/v1/conversations/{id}/messages` — non-streaming compatibility
  path; if AI is unavailable, it stores only the user note.
- `PATCH` and `DELETE /api/v1/conversations/{id}` — rename and delete.

## Provider abstraction and Ollama

The provider interface in `backend/app/chat.py` supports provider health,
model discovery, generation, and asynchronous token streaming. Ollama's
`/api/tags` response supplies installed models; `/api/chat` is used with
streaming enabled. Its NDJSON is parsed in the backend, which provides the SSE
format consumed by the frontend. Requests to localhost disable proxy use so
local traffic does not accidentally use system proxy settings.

The provider reports connectivity/model availability; this alone does not
prove that a model can generate. In the previous runtime audit Ollama listed
`gemma3:1b`, but generation crashed with a CUDA kernel compatibility error.
Do not treat the mock-provider tests or a successful health check as proof of
real inference.

## Configuration

Set these in the backend environment or root `.env` used by Compose:

| Variable | Purpose | Default |
|---|---|---|
| `AI_ENABLED` | Auto-create the Ollama provider | `false` in app settings; Compose sets `true` |
| `OLLAMA_BASE_URL` | Ollama HTTP endpoint | `http://127.0.0.1:11434`; Compose uses `host.docker.internal` |
| `OLLAMA_CHAT_MODEL` | Default chat model; `DEFAULT_MODEL` is a compatibility alias | `gemma3:1b` |
| `AI_CONTEXT_WINDOW` | Provider context-window option | `2048` |
| `AI_MAX_HISTORY_MESSAGES` | Maximum prior messages included | `8` |
| `AI_TEMPERATURE` | Generation temperature (0 through 2) | `0.3` |
| `AI_ENABLE_TOOLS` | Enable the backend's narrowly scoped prediction helper | `true` |
| `AI_ENABLE_RAG` | Feature flag reserved for RAG integration | `false` |
| `AI_STORAGE_PATH` | Local assistant data path | `local_data` |
| `AI_VECTOR_DB_PATH` | Optional Chroma persistence path | `local_data/chroma` |
| `EMBEDDING_MODEL` | Ollama embedding model name | `embeddinggemma` |
| `EMBEDDING_DIMENSION` | Expected vector dimension | `768` |
| `CHAT_PROVIDER` | Optional dotted-path custom provider class | unset |

Never commit `.env`, databases, conversation data, Chroma files, or model
weights. The checked-in `.env.example` contains local-development placeholders,
not deployment secrets.

## Prompts and application scope

The system prompt is maintained in `backend/app/prompts/car_assistant.txt`.
Conversation history is bounded by `AI_MAX_HISTORY_MESSAGES`. Requests judged
out of scope receive a fixed policy response rather than an Ollama call. The
current scope check is keyword-based and intentionally simple; it is not a
semantic classifier or a security control.

The prediction helper only returns the authenticated user's saved prediction
history. It does not expose another user's records, and it does not infer a
price denomination. Historical source rows contain fields such as model, year,
mileage, trim, transmission, body status, color, modified date, and price; they
do not include descriptions or stable source IDs.

## Optional RAG preparation

`backend/app/rag/` contains optional adapters for Ollama embeddings, a lazily
loaded Chroma vector store, dataset document construction, and idempotent
index/update/delete/reindex operations. Installation is separate:

```powershell
python -m pip install -r backend\requirements-rag.txt
```

No embedding model or Chroma package is required for ordinary chat. RAG
retrieval is not yet wired into the conversation generation path and has not
been verified with real embeddings or semantic search. Keep
`AI_ENABLE_RAG=false` until a later phase connects retrieval, tests access
boundaries and relevance, and validates the real embedding model and vector
dimension. The source price unit is undocumented; ingestion must not invent a
currency, listing description, or source identifier.

## Docker and local development

Compose starts PostgreSQL, migrations, backend, and frontend. Ollama can run
natively on the host (recommended when using an NVIDIA GPU) or through the
optional `ollama` profile. For host Ollama, set
`OLLAMA_BASE_URL=http://host.docker.internal:11434` in `.env`. For a container
Ollama profile, use `OLLAMA_BASE_URL=http://ollama:11434`; the profile does not
configure NVIDIA GPU passthrough.

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
# Edit .env: set strong secrets, AI_ENABLED=true, and a model already installed in Ollama.
docker compose config --quiet
docker compose up --build
```

The backend and frontend are at `http://localhost:8000` and
`http://localhost:3000`. To inspect services, use `docker compose ps` and
`docker compose logs -f backend`. `docker compose down -v` deletes database and
assistant volumes; do not run it if that data must be retained.

For a local backend without Compose, install `backend/requirements.txt`, set a
local `DATABASE_URL` and `JWT_SECRET_KEY`, configure Ollama variables, apply
migrations, then run `uvicorn app.main:app --app-dir backend --reload`.

## Frontend validation

The frontend package provides `test`, `lint`, and `build` scripts. On a
Node.js 24+ machine, from `frontend/`:

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

When Docker is available and a temporary, non-host-writing test environment is
preferred, mount the frontend source read-only and copy it inside the
short-lived container:

```powershell
docker run --rm -v "${PWD}\frontend:/src:ro" -w /tmp node:24-alpine sh -lc "cp -R /src /tmp/frontend && cd /tmp/frontend && npm ci && npm test && npm run lint && npm run build"
```

The host has no Node.js/npm. Docker Desktop is available, but this environment
currently receives a Docker Hub 403 when fetching base-image tokens; therefore
the frontend Node image and a fresh Compose image build could not be run. A
cached backend image was used with read-only mounts of the current backend
source and dataset to run all backend tests inside Docker.

## Test evidence and current limitations

- Backend: `python -m pytest -q` passed 38 tests on the host. The same 38 tests
  also passed in Docker using the cached backend image, with the current source
  and dataset mounted read-only and `AI_ENABLED=false`.
- Backend: `python -m compileall -q backend\app backend\tests` passed.
- Compose: `docker compose config --quiet` passed. A fresh
  `docker compose up --build` was attempted but could not fetch Docker Hub base
  image tokens (403); the pre-existing images were not treated as validation
  of the current frontend/backend build.
- Runtime smoke: current backend source, mounted into a cached backend image,
  returned healthy API status and discovered the installed `gemma3:1b` model
  through host Ollama. A real model completion/stream was not verified.
- Frontend: no test, lint, or build result is claimed; Node.js/npm are absent
  and the temporary Node image could not be fetched.
- Real AI: no genuine model-generated response has been verified. Earlier
  Ollama generation failed with a CUDA kernel compatibility error. Do not
  declare production readiness until a real completion, streamed tokens,
  cancellation, persisted conversation retrieval, frontend build, and runtime
  stack have all been verified on the target machine.
- RAG: only adapter behavior with deterministic test doubles is covered; no
  real embedding or semantic retrieval has been validated.
- Policy: keyword-based scope detection may reject relevant phrasing or allow
  irrelevant phrasing.

## RTX 4060 home-PC continuation

1. Pull the branch and install/run Ollama natively on the Windows host. Confirm
   the NVIDIA driver and Ollama runtime are healthy before testing generation.
2. Check only models already installed with `ollama list`. Choose a model
   compatible with the machine's VRAM and set `OLLAMA_CHAT_MODEL` accordingly;
   this project does not require downloading a model.
3. Start a direct generation in Ollama before testing the app. If that fails,
   resolve the Ollama/runtime issue first rather than changing app behavior.
4. Set `AI_ENABLED=true` and `OLLAMA_BASE_URL=http://host.docker.internal:11434`
   for Compose, then run the frontend and backend checks above.
5. In the UI, verify status/model discovery, select an installed model, send
   multiple messages, observe tokens arriving progressively, stop a response,
   regenerate, reload the page, and confirm completed/interrupted messages
   persist correctly.
6. Confirm user ownership by testing with two accounts. Do not enable RAG until
   real embeddings, retrieval relevance, data provenance, and access controls
   are explicitly validated.

## File reference

- Provider and Ollama HTTP/SSE source: `backend/app/chat.py`
- FastAPI startup and provider/model endpoints: `backend/app/main.py`
- Authenticated conversation routes and prompt context: `backend/app/routes/conversations.py`
- Prompt assembly and scope policy: `backend/app/services/assistant.py`
- User-scoped prediction helper: `backend/app/services/prediction_tools.py`
- Stream persistence and event framing: `backend/app/services/streaming.py`
- System prompt: `backend/app/prompts/car_assistant.txt`
- Optional embeddings/vector/index adapters: `backend/app/rag/`
- Frontend chat and history: `frontend/src/App.tsx`
- Frontend SSE reader: `frontend/src/services/chatStream.ts`
- Backend behavioral tests: `backend/tests/test_chat_streaming.py`,
  `test_assistant_services.py`, and `test_rag_pipeline.py`
