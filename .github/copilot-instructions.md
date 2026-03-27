# Copilot Instructions for Hybrid AI Platform

## Quick Start

**Setup:**
```bash
make bootstrap  # Creates venv and installs the package in dev mode
```

**Run the assistant:**
```bash
python -m app --prompt "Your prompt here"
# or after install: hybrid-assistant --prompt "Your prompt here"
```

**Run tests/validation:**
```bash
make verify  # Compiles all Python modules, catching syntax errors
```

**Test a single Bedrock call:**
```bash
make run  # Runs a predefined prompt against Bedrock
```

## Architecture Overview

This is a **hybrid development environment** where the laptop stays lightweight and Bedrock handles inference.

```
Local workstation (Terraform CLI + Python CLI)
    ↓
AWS Account (Bedrock inference, S3 assets, CloudWatch logs, IAM runtime role)
```

**Key principle:** The laptop is for development and orchestration, not model hosting. All inference goes through Amazon Bedrock's Converse API.

### Core components:

1. **app/** - Python CLI assistant that sends prompts to Bedrock
   - `main.py`: Entry point with CLI arg parsing and error handling
   - `config/settings.py`: Environment configuration loader (supports `.env` files with validation)
   - `clients/bedrock.py`: Bedrock SDK wrapper with boto3 session and retry logic
   - `services/chat.py`: High-level chat service that invokes Bedrock and formats responses

2. **infra/** - Terraform for AWS baseline
   - Creates S3 bucket (encrypted, for prompt/artifact storage)
   - Creates CloudWatch log group (for future hosted workloads)
   - Creates IAM runtime role (Bedrock + S3 + CloudWatch permissions)

3. **docs/** - Architecture records and setup guidance

## Key Conventions

### Configuration Pattern

Settings are loaded from a `.env` file using a custom loader in `app.config.settings`:
- Required variables (with validation): `AWS_REGION`, `BEDROCK_MODEL_ID` or `BEDROCK_INFERENCE_PROFILE_ARN`
- Optional variables with defaults: `LOG_LEVEL=INFO`, `BEDROCK_MAX_TOKENS=1024`, `BEDROCK_TEMPERATURE=0.2`
- The loader validates types (int, float, log level) and raises `SettingsError` with clear messages if validation fails
- Supports `export KEY=value` syntax in `.env` files

When adding new configuration:
- Define as `_optional_env()` or `_required_env()` in `settings.py`
- Add a validated property or use a custom validator (see `_int_env`, `_float_env`, `_log_level_env` for patterns)
- Add a default in `.env.example`

### Error Handling

- `SettingsError` for configuration issues (caught in `main.py`, exit code 2)
- `BedrockClientError` for Bedrock invocation failures (caught in `main.py`, exit code 1)
- Logs include structured data: `aws_region`, `model_id`, `request_id`, `latency_ms`, `input_tokens`, `output_tokens`

### Logging

Uses Python's standard `logging` module configured in `app.config.logging`:
- `stderr`: Structured JSON logs (with timestamp, level, service name, environment)
- `stdout`: Only the assistant response text (unless `--json` flag is used)
- `LOG_LEVEL` env var controls verbosity (CRITICAL, ERROR, WARNING, INFO, DEBUG)

### CLI Argument Handling

- `--prompt`: User message (required if stdin is empty)
- `--system`: Override system prompt (optional)
- `--max-tokens`, `--temperature`: Override model parameters at runtime
- `--json`: Print full response payload instead of just text
- `--env-file`: Custom `.env` path (defaults to `.env`)
- stdin support: If `--prompt` is omitted and stdin is not a TTY, reads from stdin

### AWS Credentials

The app uses boto3 with AWS profiles:
- `AWS_PROFILE` selects which named profile to use
- `AWS_REGION` must match a region where the Bedrock model is available
- No automatic IAM role assumption for local runs; uses the local profile's credentials

## Bedrock Integration

**Runtime model selection (property `runtime_model_identifier`):**
- Prefers `BEDROCK_INFERENCE_PROFILE_ARN` if set (for cross-region inference profiles)
- Falls back to `BEDROCK_MODEL_ID` (direct model ID like `anthropic.claude-3-5-sonnet-20241022-v2:0`)
- Raises `SettingsError` if neither is set

**Converse API:**
- Uses boto3's `bedrock-runtime` client
- Sends `messages` (user/assistant turns), `system` prompt, `max_tokens`, and `temperature`
- Extracts response text, stop reason, usage tokens, and request ID from the response
- Retry policy: standard mode, 3 attempts, 10s connect timeout, 120s read timeout

**Response structure (`BedrockResponse`):**
- `text`: Full assistant response
- `stop_reason`: Why the model stopped (e.g., "end_turn", "max_tokens")
- `usage_input_tokens`, `usage_output_tokens`: Token counts for billing tracking
- `request_id`: AWS request ID for debugging

## Future Extension Points

These are preserved in the architecture but not yet implemented:

- **S3 persistence:** Prompt and result archiving (S3 bucket already provisioned by Terraform)
- **API layer:** FastAPI service on top of `app.services` for hosted runtimes
- **Streaming responses:** Replace Converse API with stream variant
- **Multiple message turns:** Persist conversation state, build multi-turn chat
- **Bedrock Guardrails:** Add content filtering and safety checks
- **Hosted execution:** Lambda or ECS tasks that assume the Terraform-created IAM runtime role

## Environment-Specific Notes

- **Local development**: Uses laptop AWS profile credentials; Terraform creates infra in your AWS account
- **CI/CD**: Not yet configured; would benefit from GitHub Actions running `make verify` on pushes
- **State management:** Terraform state is local (`infra/environments/dev/.terraform/`); for team workflows, move to S3 + DynamoDB

## Troubleshooting Checklist

- **"AWS credential issues"**: Run `aws sts get-caller-identity --profile <profile>` to verify credentials
- **"Missing BEDROCK_MODEL_ID"**: The model must exist in your AWS account and region
- **"Region mismatch"**: Ensure `AWS_REGION` in `.env` and the profile's default region match your model's region
- **"Invalid LOG_LEVEL"**: Must be one of: CRITICAL, ERROR, WARNING, INFO, DEBUG

## Development Tips

- **Local testing**: `make run` or `make example` use predefined prompts
- **Custom prompts:** `python -m app --system "Custom instructions" --prompt "Your question"`
- **JSON responses:** `python -m app --prompt "Question" --json` for programmatic parsing
- **Verify syntax:** `make verify` compiles all Python before running
- **Check code structure:** `make tree` displays the repository layout
- **Terraform formatting:** `make terraform-fmt` auto-formats HCL files
