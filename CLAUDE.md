# TK-AI

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
make frontend-bootstrap # npm install
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
  clients/
    base.py             # AssistantClient protocol
    anthropic.py        # AnthropicRuntimeClient (direct API fallback)
    bedrock.py          # BedrockRuntimeClient (primary, streaming + guardrails)
    __init__.py         # Factory: create_runtime_client()
  config/
    settings.py         # Immutable Settings dataclass (env-driven, from_env())
    logging.py          # JSON structured logging
  services/
    chat.py             # ChatService — context trimming, message prep, metadata
  server.py             # ThreadingHTTPServer — REST API + SSE streaming
  session_store.py      # SQLite session/message persistence (versioned schema)
  main.py               # CLI entry point
desktop/
  electron/
    main.cjs            # Electron main process — spawns Python server subprocess
    db-path.cjs         # Database path resolution
    preload.cjs         # IPC bridge (assistantApi)
  src/
    App.jsx             # Root React component (~1350 lines)
    main.jsx            # React entry point
    layout.js           # Responsive sidebar/workspace layout
    transcript.js       # Transcript export utilities
    styles.css          # Comprehensive styling (~1200 lines)
    *.test.jsx/js       # Vitest component tests
  assets/               # App icons (PNG, ICO, ICNS, SVG)
infra/
  stacks/
    platform_baseline_stack.py  # CDK stack (S3, CloudWatch, IAM)
    config.py           # Stack configuration
  app.py                # CDK app entry point
scripts/                # Deployment & smoke-test helpers
tests/                  # Python unit tests (unittest)
```

## Key patterns

- **Provider abstraction:** `AssistantClient` protocol in `app/clients/base.py` with Bedrock and Anthropic implementations. Factory: `create_runtime_client()` selects based on `AI_PROVIDER` env var.
- **Streaming:** True provider-backed streaming via SSE. Bedrock client streams via ConverseStream API; server exposes `/api/chat` with `Accept: text/event-stream` for SSE or JSON for non-streaming.
- **Context trimming:** `ChatService` trims conversation history by max turns and max chars before sending to provider. Configurable via `CONTEXT_WINDOW_MAX_TURNS` and `CONTEXT_WINDOW_MAX_CHARS`.
- **Settings:** Immutable frozen dataclass in `app/config/settings.py`, loaded from env vars via `Settings.from_env()`. Validates and resolves Bedrock inference profiles vs direct model IDs.
- **Session store:** SQLite via stdlib `sqlite3` with schema versioning and forward migrations. Tables: `sessions`, `messages`. Default path: `~/.config/{app}/assistant.db`.
- **Desktop integration:** Electron spawns the Python server as a subprocess, communicates over localhost HTTP. React frontend consumes SSE for streaming responses.

## Environment

Configuration lives in `.env` at repo root (see `.env.example` for full reference). Key variables:

- `AI_PROVIDER` — `bedrock` or `anthropic`
- `AWS_REGION`, `AWS_PROFILE` — AWS config
- `BEDROCK_INFERENCE_PROFILE_ARN`, `BEDROCK_INFERENCE_PROFILE_ID` — preferred Bedrock target (cross-region)
- `BEDROCK_MODEL_ID` — fallback direct model ID
- `ANTHROPIC_API_KEY` — for direct Anthropic fallback
- `MODEL_MAX_TOKENS`, `MODEL_TEMPERATURE` — generation params
- `CONTEXT_WINDOW_MAX_TURNS`, `CONTEXT_WINDOW_MAX_CHARS` — trimming limits
- `BEDROCK_GUARDRAIL_*` — optional guardrail config
- `ASSISTANT_SYSTEM_PROMPT` — customizable system prompt text

## API endpoints

- `GET  /api/health` — health check with provider info
- `GET  /api/sessions` — list all sessions
- `GET  /api/sessions/{id}` — get session with messages
- `POST /api/sessions` — create new session
- `PATCH /api/sessions/{id}` — rename session
- `DELETE /api/sessions/{id}` — delete session
- `POST /api/chat` — send message (JSON response or SSE stream)

## Git workflow

- `dev` is the integration branch; `main` is stable
- Topic branches merge into `dev`, not directly into `main`
- `dev` promotes to `main` when validated
- Branch naming: `{issue#}-{slug}` (e.g. `10-add-true-provider-backed-streaming`)

## CI

GitHub Actions workflow (`.github/workflows/smoke.yml`):
- **local-smoke** (always): Python 3.12 + Node 20, `make smoke`
- **live-bedrock-smoke** (manual): AWS OIDC, live Bedrock invocation
- **deployed-stack-smoke** (manual): CloudFormation stack verification

## Conventions

- Python: PEP-8 style, no explicit linter configured yet
- JavaScript: no eslint/prettier configured yet
- Tests: Python in `tests/`, React in `desktop/src/*.test.{js,jsx}`
- No Docker — desktop app packaged via electron-builder
- Issues tracked in GitHub Issues with the following metadata:
  - **Assignee:** `justactnatural`
  - **Labels:** from `bug`, `enhancement`, `ui/ux`, `data layer`, `backend`
  - **Type:** `Bug`, `Feature`, or as appropriate
  - **Project:** "Hybrid AI Platform Roadmap" (set status to "In Progress" when work begins)
  - **Milestone:** `complete desktop app` (current active milestone)
- PRs should reference their issue (`Closes #N`) and target `dev`
