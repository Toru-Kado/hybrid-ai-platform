# Hybrid AI Platform

## Project overview

Monorepo for a local-first AI assistant with an Electron desktop shell and an AWS infrastructure baseline.

- **Backend:** Python 3.12+ CLI + HTTP server (`app/`)
- **Frontend:** React 19 + Electron 39 desktop app (`desktop/`)
- **Infrastructure:** AWS CDK in Python (`infra/`)
- **Primary AI runtime:** AWS Bedrock (Claude models); Anthropic direct API as fallback

## Quick reference

```bash
# First-time setup
make bootstrap          # Python venv + app install
make frontend-bootstrap # npm install (alias: npm install)
make infra-bootstrap    # Infra venv + CDK libs

# Daily development
make desktop-api        # Start Python API server (127.0.0.1:8765)
make desktop-dev        # Vite dev server + Electron (port 5173)
make run                # One-shot CLI prompt

# Testing
make test               # Python unittest (tests/)
make verify             # compile + test
npm run desktop:test    # Vitest for React components
make infra-test         # pytest for CDK stack tests

# Smoke tests
make smoke              # Local: verify + infra-test + cdk-synth
make smoke-bedrock      # Live Bedrock invocation
make smoke-stack        # Verify deployed CloudFormation stack

# Build & package
make desktop-build      # Vite production build
make desktop-pack       # Build + electron-builder --dir

# Infrastructure
make cdk-synth          # Synthesize CDK to CloudFormation
make cdk-diff           # Show CDK changes
make cdk-deploy         # Deploy via scripts/deploy-baseline.sh
```

## Architecture

```
app/
  clients/              # AssistantClient protocol + Bedrock/Anthropic impls
  config/               # Settings (env-driven dataclass), logging (JSON)
  services/             # ChatService wraps client calls
  server.py             # ThreadingHTTPServer — REST API
  session_store.py      # SQLite session/message persistence
  main.py               # CLI entry point
desktop/
  electron/main.cjs     # Electron main process — spawns Python server
  src/
    App.jsx             # Root React component
    main.jsx            # React entry point
    layout.js           # Responsive sidebar/workspace layout
infra/
  platform_baseline/    # CDK stack (S3, CloudWatch, IAM)
  app.py                # CDK app entry point
scripts/                # Deployment & smoke-test helpers
tests/                  # Python unit tests (unittest)
```

## Key patterns

- **Provider abstraction:** `AssistantClient` protocol in `app/clients/` with `BedrockRuntimeClient` and `AnthropicRuntimeClient` implementations. Factory: `create_runtime_client()` selects based on `AI_PROVIDER` env var.
- **Settings:** Immutable dataclass in `app/config/settings.py`, loaded from env vars via `Settings.from_env()`. Validates and resolves Bedrock inference profiles vs direct model IDs.
- **API server:** Custom `ThreadingHTTPServer` in `app/server.py`. Routes: `/api/health`, `/api/sessions[/{id}]`, `/api/chat`. JSON request/response. 128KB max request size.
- **Session store:** SQLite via stdlib `sqlite3` in `app/session_store.py`. Tables: `sessions`, `messages`. Default path: `~/.config/{app}/assistant.db`.
- **Desktop integration:** Electron spawns the Python server as a subprocess, communicates over localhost HTTP.

## Environment

Configuration lives in `.env` at repo root (see `.env.example` for full reference). Key variables:

- `AI_PROVIDER` — `bedrock` or `anthropic`
- `AWS_REGION`, `AWS_PROFILE` — AWS config
- `BEDROCK_INFERENCE_PROFILE_ARN` — preferred Bedrock target
- `ANTHROPIC_API_KEY` — for direct Anthropic fallback
- `MODEL_MAX_TOKENS`, `MODEL_TEMPERATURE` — generation params

## Git workflow

- `dev` is the integration branch; `main` is stable
- Topic branches merge into `dev`, not directly into `main`
- `dev` promotes to `main` when validated

## CI

GitHub Actions workflow (`.github/workflows/smoke.yml`):
- **local-smoke** (always): Python 3.12 + Node 20, `make smoke`
- **live-bedrock-smoke** (manual): AWS OIDC, live Bedrock invocation
- **deployed-stack-smoke** (manual): CloudFormation stack verification

## Conventions

- Python: PEP-8 style, no explicit linter configured yet
- JavaScript: no eslint/prettier configured yet
- Tests colocated: Python in `tests/`, React in `desktop/src/*.test.{js,jsx}`
- No Docker — desktop app packaged via electron-builder
