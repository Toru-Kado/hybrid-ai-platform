# Hybrid AI Platform

Starter repository for a hybrid AI development setup with:

- Intel Core i9 MacBook Pro for local development
- AWS for infrastructure
- Anthropic Claude through Amazon Bedrock or the direct Anthropic API
- Terraform for cloud resources
- Python 3.12 for a small assistant CLI

This repo is intentionally small. The laptop is for development and orchestration. The runtime can be Bedrock or Anthropic directly.

## What This Repo Creates

- [app](/Users/nathanmalitz/Code/hybrid-ai-platform/app): Python CLI that sends prompts to Claude through the selected provider
- [infra](/Users/nathanmalitz/Code/hybrid-ai-platform/infra): Terraform for an S3 bucket, CloudWatch log group, and IAM runtime role
- [docs](/Users/nathanmalitz/Code/hybrid-ai-platform/docs): architecture notes and setup guidance

## Prerequisites

- Python `3.12`
- Terraform `>= 1.7`
- AWS CLI v2
- One of:
- An AWS account with Bedrock access in your chosen region
- An Anthropic API key

## Step-By-Step Setup

### 1. Configure local AWS access

Skip this step if you plan to run with `AI_PROVIDER=anthropic`.

Create a profile and verify it:

```bash
aws configure --profile hybrid-ai-dev
aws sts get-caller-identity --profile hybrid-ai-dev
```

Use a region where Bedrock and your Claude model are enabled.

If you want a thinner IAM user, create a separate operator role in Terraform and let
your local user assume it. The runtime role in this repo stays separate.

With the optional operator role enabled, a common profile split looks like:

```ini
[profile hybrid-ai-bootstrap]
region = us-east-1

[profile hybrid-ai-dev]
region = us-east-1
source_profile = hybrid-ai-bootstrap
role_arn = arn:aws:iam::929924811789:role/HybridAIDevOperatorRole
```

In that setup:

- `hybrid-ai-bootstrap` is the thin IAM user profile
- `hybrid-ai-dev` is the assumed role profile you use in `.env` and Terraform

### 2. Create local app configuration

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `AI_PROVIDER`
- if `AI_PROVIDER=bedrock`:
- `AWS_REGION`
- `AWS_PROFILE`
- `BEDROCK_MODEL_ID` or `BEDROCK_INFERENCE_PROFILE_ID` or `BEDROCK_INFERENCE_PROFILE_ARN`
- optional: `BEDROCK_GUARDRAIL_IDENTIFIER` + `BEDROCK_GUARDRAIL_VERSION`
- if `AI_PROVIDER=anthropic`:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

Bedrock example:

```dotenv
AI_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_PROFILE=hybrid-ai-dev
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
```

Anthropic example:

```dotenv
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-5
```

### 3. Install the Python app

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Equivalent shortcut:

```bash
make bootstrap
```

### 4. Create the AWS baseline with Terraform

Copy the example tfvars file:

```bash
cp infra/environments/dev/terraform.tfvars.example infra/environments/dev/terraform.tfvars
```

Review these values before apply:

- `aws_region`
- `aws_profile`
- `bedrock_allowed_model_ids`
- `bedrock_allowed_inference_profile_arns`
- `bedrock_allowed_guardrail_arns`
- `runtime_role_trusted_principal_arns`
- `operator_user_name`
- `ai_assets_bucket_force_destroy`

Then run Terraform:

```bash
make terraform-init
make terraform-plan
make terraform-apply
```

Terraform creates:

- An encrypted S3 bucket for prompts, datasets, and generated artifacts
- A CloudWatch log group for assistant-related workloads
- An IAM role for future Bedrock-powered AWS runtimes
- Optional: a separate IAM operator role for local development, plus a small inline
  policy on an existing IAM user that allows `sts:AssumeRole`

If you plan to use Bedrock guardrails, add the target guardrail ARN to
`bedrock_allowed_guardrail_arns`.

If you set `operator_user_name`, Terraform does not create that IAM user for you.
It assumes the user already exists, then grants that user permission to assume the
new operator role. This keeps local operator access separate from the runtime role.

### 5. Copy useful Terraform outputs into `.env`

Get outputs:

```bash
terraform -chdir=infra/environments/dev output
```

Copy these values into `.env` if you want local references to the provisioned resources:

- `ai_assets_bucket_name` -> `AI_ASSETS_BUCKET_NAME`
- `assistant_log_group_name` -> `ASSISTANT_LOG_GROUP_NAME`
- `aws_region` -> `AWS_REGION`

The local CLI uses your active AWS credentials directly. It does not automatically assume the Terraform-created IAM role.

If your AWS profile already assumes the Terraform-created operator role, the CLI will
use that role automatically through the standard AWS SDK profile chain.

## First Run

Check the CLI wiring first:

```bash
python -m app --help
```

Then send a prompt:

```bash
python -m app --prompt "Summarize why this repo uses Bedrock instead of local model inference."
```

Direct Anthropic example:

```bash
AI_PROVIDER=anthropic python -m app --prompt "Summarize why this repo keeps a direct Anthropic fallback."
```

Or, after install:

```bash
hybrid-assistant --prompt "List two extension ideas for this starter."
```

## Optional Bedrock Guardrails

Bedrock guardrails are optional in this starter.

- If you leave `BEDROCK_GUARDRAIL_IDENTIFIER` and `BEDROCK_GUARDRAIL_VERSION` empty, the app sends plain `Converse` requests with no `guardrailConfig`.
- If you set them, the app can attach guardrails selectively.

`BEDROCK_GUARDRAIL_MODE` supports:

- `off`
  Omit Bedrock guardrails completely.
- `user`
  Attach Bedrock guardrails and assess only the user prompt.
- `all`
  Attach Bedrock guardrails and assess both the user prompt and the system prompt.

You can override this per run:

```bash
python -m app --guardrails user --prompt "Review this customer-facing response."
python -m app --guardrails off --prompt "Summarize these internal architecture notes."
```

When `AI_PROVIDER=bedrock`, this gives you a simple layered model:

- custom application logic
- optional Bedrock guardrails
- model-level safety defaults

## Example Commands

Basic prompt:

```bash
python -m app --prompt "Explain the purpose of the S3 bucket in this repo."
```

Custom system prompt:

```bash
python -m app \
  --system "You are a senior cloud architect." \
  --prompt "Propose the next two improvements for this platform."
```

JSON output:

```bash
python -m app --prompt "List three common runtime setup mistakes." --json
```

Prompt from stdin:

```bash
echo "Describe the role of CloudWatch in this repo." | python -m app
```

## Expected Output

Normal mode:

- Assistant text is printed to `stdout`
- Structured logs are printed to `stderr`

Example shape:

```text
This repository keeps local development lightweight and pushes model inference to Amazon Bedrock.
```

JSON log example:

```json
{"timestamp":"2026-03-27T00:00:00+00:00","level":"INFO","logger":"app.services.chat","message":"Model prompt completed","service":"hybrid-ai-assistant","environment":"dev","provider":"bedrock","aws_region":"us-east-1","target_id":"us.anthropic.claude-opus-4-6-v1","target_kind":"inference_profile","target_source":"BEDROCK_INFERENCE_PROFILE_ID","guardrail_mode":"user","guardrail_identifier":"gr-abc123","guardrail_applied":true,"guardrail_intervened":false,"request_id":"...","latency_ms":1234}
```

With `--json`, the assistant prints a response object like:

```json
{
  "response_text": "...",
  "provider": "bedrock",
  "target_id": "...",
  "target_kind": "inference_profile",
  "target_source": "BEDROCK_INFERENCE_PROFILE_ID",
  "guardrail_mode": "user",
  "guardrail_identifier": "gr-abc123",
  "guardrail_applied": true,
  "guardrail_intervened": false,
  "stop_reason": "...",
  "service_tier": "...",
  "input_tokens": 123,
  "output_tokens": 456,
  "request_id": "...",
  "latency_ms": 1234
}
```

## Common Failure Points

### AWS credential issues

- `AWS_PROFILE` points to a profile that does not exist
- AWS CLI credentials are expired or missing
- You can diagnose this with `aws sts get-caller-identity --profile <profile>`

### Bedrock access not enabled

- The account has not been granted access to the Claude model you selected
- The IAM identity can authenticate to AWS but cannot call Bedrock
- Bedrock may return access denied or model not found errors
- Some Claude models require an inference profile instead of direct on-demand model invocation
- `ThrottlingException: Too many tokens per day` indicates the account or profile hit Bedrock daily token quota
- If you are using `BEDROCK_INFERENCE_PROFILE_ID`, your AWS identity must also be allowed to invoke the matching inference profile
- If you are using `BEDROCK_INFERENCE_PROFILE_ARN`, your AWS identity must also be allowed to invoke that exact inference profile ARN
- If you are using Bedrock guardrails, your AWS identity must also be allowed to apply the exact guardrail ARN

### Anthropic API issues

- `ANTHROPIC_API_KEY` is missing or invalid
- The selected `ANTHROPIC_MODEL` is not available to the account
- Anthropic may return rate-limit errors independently of AWS

### Region mismatch

- `.env` points at one region while Terraform or your AWS profile uses another
- The selected model exists in a different region than `AWS_REGION`

### Missing environment variables

- `AI_PROVIDER` must be `bedrock` or `anthropic`
- `AWS_REGION` is required for `AI_PROVIDER=bedrock`
- `BEDROCK_MODEL_ID`, `BEDROCK_INFERENCE_PROFILE_ID`, or `BEDROCK_INFERENCE_PROFILE_ARN` is required for `AI_PROVIDER=bedrock`
- `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` are required for `AI_PROVIDER=anthropic`
- `BEDROCK_MODEL_ID` must be a plain model ID, not an ARN
- `BEDROCK_INFERENCE_PROFILE_ID` must be a profile ID, not an ARN
- Set only one of `BEDROCK_INFERENCE_PROFILE_ID` or `BEDROCK_INFERENCE_PROFILE_ARN`
- If you set one of `BEDROCK_GUARDRAIL_IDENTIFIER` or `BEDROCK_GUARDRAIL_VERSION`, set both
- `BEDROCK_GUARDRAIL_MODE` must be one of `off`, `user`, or `all`
- Invalid `LOG_LEVEL`, `MODEL_MAX_TOKENS`, or `MODEL_TEMPERATURE` values fail fast during startup

## How The Pieces Fit Together

- `infra/` creates the AWS baseline resources
- `app/` reads `.env`, then calls Bedrock through `boto3` or Anthropic through direct HTTPS
- `docs/` explains the operating model and local tool assumptions

Useful references:

- [architecture.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/architecture.md)
- [bedrock-claude-notes.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/bedrock-claude-notes.md)
- [kilo-code-setup.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/kilo-code-setup.md)

## Future Extensions

- Persist prompts and results to S3
- Add streaming responses
- Add a small API layer on top of `app/services`
- Add CI checks for Python and Terraform
