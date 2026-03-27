# Hybrid AI Platform

Production-minded starter repository for a hybrid AI development environment built around:

- An Intel Core i9 MacBook Pro for local development and orchestration
- AWS as the cloud platform
- Anthropic Claude through Amazon Bedrock as the primary AI runtime
- Terraform for infrastructure management
- Python 3.12 for assistant workflows and backend automation
- Kilo Code configured to use AWS Bedrock

The design is intentionally simple: local development stays lightweight, while model execution and shared assets live in AWS.

## Repository Layout

```text
.
├── app/                     # Python assistant application
├── docs/                    # Architecture, setup, and decision records
├── infra/                   # Terraform modules and dev environment
├── .env.example             # Environment variables for local development
├── .gitignore
├── Makefile
├── pyproject.toml           # Python packaging and CLI entrypoint
└── README.md
```

## Architecture Summary

- The MacBook Pro is used for coding, Terraform execution, CLI usage, and light orchestration.
- Amazon Bedrock handles Claude inference so the local machine does not carry model runtime costs.
- S3 stores prompts, exports, evaluation data, or other AI assets.
- CloudWatch Log Groups provide a destination for runtime logs when you later wire in hosted components.
- A dedicated IAM role scopes Bedrock, S3, and CloudWatch permissions for the assistant runtime.

See [architecture.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/architecture.md) for the full breakdown.

## Prerequisites

- Python `3.12`
- Terraform `>= 1.7`
- AWS CLI v2
- Access to Amazon Bedrock in your selected AWS region
- Permission to create IAM, S3, and CloudWatch resources in your AWS account

## Local Setup

1. Copy `.env.example` to `.env`.
2. Create and activate a virtual environment.
3. Install the package in editable mode.

```bash
cp .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

If you prefer `make`:

```bash
make bootstrap
```

## Configure AWS

Use an AWS profile with Bedrock access in the region where your chosen Claude model is enabled.

Example:

```bash
aws configure --profile hybrid-ai-dev
aws sts get-caller-identity --profile hybrid-ai-dev
```

Set `AWS_PROFILE` and `AWS_REGION` in `.env` to match that profile.

## Terraform Workflow

The `dev` environment is under [infra/environments/dev](/Users/nathanmalitz/Code/hybrid-ai-platform/infra/environments/dev).

1. Copy the example variables file.
2. Review the Bedrock model IDs and trusted principals.
3. Initialize and apply Terraform.

```bash
cp infra/environments/dev/terraform.tfvars.example infra/environments/dev/terraform.tfvars
make terraform-init
make terraform-plan
make terraform-apply
```

Terraform creates:

- An encrypted S3 bucket for AI assets
- A CloudWatch log group for assistant logs
- An IAM role for Bedrock, S3, and logging access

After `apply`, capture the outputs and copy the bucket and log group values into `.env`.

## Run The Python Assistant

Basic prompt:

```bash
python -m app --prompt "Summarize the tradeoffs of using Bedrock from a local Intel Mac."
```

Prompt with a custom system instruction:

```bash
python -m app \
  --system "You are a cloud architecture assistant." \
  --prompt "Propose a lightweight AI platform roadmap for a solo developer."
```

Structured JSON output:

```bash
python -m app --prompt "List three AWS Bedrock guardrail ideas." --json
```

## How It Fits Together

- `infra/` provisions the AWS primitives the platform needs first.
- `app/` reads environment configuration and uses `boto3` to call Bedrock's Converse API.
- `docs/` captures the operating model, constraints, and future evolution points.
- Kilo Code can reuse the same AWS profile and region choices documented in [kilo-code-setup.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/kilo-code-setup.md).

## Extension Points

- Add prompt persistence and artifact upload flows to S3
- Introduce evaluation jobs or async processing with Lambda or ECS
- Add Bedrock Guardrails and tracing
- Promote Terraform state to a remote backend for team usage
- Add CI checks for Terraform validation and Python linting

## Manual Follow-Up

- Enable the desired Claude model in Amazon Bedrock for your AWS account and region
- Review the IAM role trust policy inputs before using it beyond local development
- Decide whether local AWS profiles will call Bedrock directly or assume the created runtime role
