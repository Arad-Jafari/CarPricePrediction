# Peugeot 206 frontend

React, TypeScript, and Vite application for the Peugeot 206 estimate platform.
The authenticated workspace includes prediction history, comparison, profile,
and a local-AI conversation interface.

## Development

Use Node.js 24+ from this directory:

```powershell
npm.cmd ci
npm.cmd run dev
```

The Vite development server proxies `/api` requests to the FastAPI backend at
`http://localhost:8000`. Configure and start the backend using the repository
root or backend README instructions.

## Checks

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

The chat UI displays provider/model status from `/api/v1/model/info`; it does
not pretend a reply exists when the local provider is unavailable. The stream
reader and conversation UI tests use mocked HTTP responses, not a live Ollama
model. See [the assistant validation guide](../docs/ai-assistant/README.md) for
real runtime and temporary-container testing instructions.
