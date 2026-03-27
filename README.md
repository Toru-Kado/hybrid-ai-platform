# Hybrid AI Platform

Starter repository for a hybrid AI development setup with:

- Intel Core i9 MacBook Pro for local development
- AWS for infrastructure
- Anthropic Claude on Amazon Bedrock as the primary model runtime
- Terraform for cloud resources
- Python 3.12 for a small assistant CLI

This repo is intentionally small. The laptop is for development and orchestration. Bedrock is the runtime.

## What This Repo Creates

- [app](/Users/nathanmalitz/Code/hybrid-ai-platform/app): Python CLI that sends prompts to Bedrock Claude
- [infra](/Users/nathanmalitz/Code/hybrid-ai-platform/infra): Terraform for an S3 bucket, CloudWatch log group, and IAM runtime role
- [docs](/Users/nathanmalitz/Code/hybrid-ai-platform/docs): architecture notes and setup guidance

## Prerequisites

- Python `3.12`
- Terraform `>= 1.7`
- AWS CLI v2
- An AWS account with Bedrock access in your chosen region
- Access to at least one Claude model in that region

## Step-By-Step Setup

### 1. Configure local AWS access

Create a profile and verify it:

```bash
aws configure --profile hybrid-ai-dev
aws sts get-caller-identity --profile hybrid-ai-dev
```

Use a region where Bedrock and your Claude model are enabled.

### 2. Create local app configuration

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `AWS_REGION`
- `AWS_PROFILE`
- `BEDROCK_MODEL_ID` or `BEDROCK_INFERENCE_PROFILE_ARN`
- optional: `BEDROCK_GUARDRAIL_IDENTIFIER` + `BEDROCK_GUARDRAIL_VERSION`

Example:

```dotenv
AWS_REGION=us-east-1
AWS_PROFILE=hybrid-ai-dev
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
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

If you plan to use Bedrock guardrails, add the target guardrail ARN to
`bedrock_allowed_guardrail_arns`.

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

## First Run

Check the CLI wiring first:

```bash
python -m app --help
```

Then send a prompt:

```bash
python -m app --prompt "Summarize why this repo uses Bedrock instead of local model inference."
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

This gives you a simple layered model:

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
python -m app --prompt "List three common Bedrock setup mistakes." --json
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
{"timestamp":"2026-03-27T00:00:00+00:00","level":"INFO","logger":"app.services.chat","message":"Bedrock prompt completed","service":"hybrid-ai-assistant","environment":"dev","aws_region":"us-east-1","model_id":"anthropic.claude-3-5-sonnet-20241022-v2:0","guardrail_mode":"user","guardrail_identifier":"gr-abc123","guardrail_applied":true,"guardrail_intervened":false,"request_id":"...","latency_ms":1234}
```

With `--json`, the assistant prints a response object like:

```json
{
  "response_text": "...",
  "model_id": "...",
  "guardrail_mode": "user",
  "guardrail_identifier": "gr-abc123",
  "guardrail_applied": true,
  "guardrail_intervened": false,
  "stop_reason": "...",
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
- If you are using `BEDROCK_INFERENCE_PROFILE_ARN`, your AWS identity must also be allowed to invoke that exact inference profile ARN
- If you are using Bedrock guardrails, your AWS identity must also be allowed to apply the exact guardrail ARN

### Region mismatch

- `.env` points at one region while Terraform or your AWS profile uses another
- The selected model exists in a different region than `AWS_REGION`

### Missing environment variables

- `AWS_REGION` is required
- `BEDROCK_MODEL_ID` or `BEDROCK_INFERENCE_PROFILE_ARN` is required
- `BEDROCK_MODEL_ID` must be a plain model ID, not an ARN
- If you set one of `BEDROCK_GUARDRAIL_IDENTIFIER` or `BEDROCK_GUARDRAIL_VERSION`, set both
- `BEDROCK_GUARDRAIL_MODE` must be one of `off`, `user`, or `all`
- Invalid `LOG_LEVEL`, `BEDROCK_MAX_TOKENS`, or `BEDROCK_TEMPERATURE` values fail fast during startup

## How The Pieces Fit Together

- `infra/` creates the AWS baseline resources
- `app/` reads `.env`, uses your AWS credentials, and calls Bedrock through `boto3`
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
