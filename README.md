# Hybrid AI Platform

Hybrid AI starter for:

- local Python-based assistant workflows
- Amazon Bedrock as the primary model runtime
- AWS CDK as the infrastructure baseline
- the Toru Kado AWS organization segment

This repo has been reset away from Terraform. The IaC source of truth is now the CDK app under [infra](/Users/nathanmalitz/Code/hybrid-ai-platform/infra), and deploys should target the same AWS org/account path already being used in `fooocus-rig`.

## What This Repo Contains

- [app](/Users/nathanmalitz/Code/hybrid-ai-platform/app): Python CLI for prompting Claude through Amazon Bedrock
- [desktop](/Users/nathanmalitz/Code/hybrid-ai-platform/desktop): React and Electron desktop POC
- [infra](/Users/nathanmalitz/Code/hybrid-ai-platform/infra): Python AWS CDK app for the shared AWS baseline
- [scripts](/Users/nathanmalitz/Code/hybrid-ai-platform/scripts): local helpers for CDK bootstrap and deploy
- [docs](/Users/nathanmalitz/Code/hybrid-ai-platform/docs): architecture, Bedrock notes, and operator guidance

## Infrastructure Baseline

The CDK stack currently provisions:

- an encrypted S3 bucket for prompts, datasets, exports, and generated assets
- a CloudWatch log group for assistant workloads
- an IAM runtime role for future Bedrock-powered hosted execution
- an optional IAM operator role for local development access

The stack applies these baseline tags:

- `Company=Toru Kado`
- `Project=hybrid-ai-platform`
- `ManagedBy=aws-cdk`
- `OrganizationSegment=toru-kado`

## Prerequisites

- Python `3.12`
- AWS CLI v2
- Node.js plus the AWS CDK CLI (`cdk`)
- an AWS profile that resolves to the intended Toru Kado account

If you are using AWS IAM Identity Center, verify the target account before bootstrapping or deploying:

```bash
aws sts get-caller-identity --profile TK-Admin
```

Use the profile that resolves to the same AWS organization segment and account path you are already using for `fooocus-rig`. Do not assume an old `hybrid-ai-dev` account or role still applies.

## Local App Setup

Create the app environment and install the Python package:

```bash
make bootstrap
npm install
cp .env.example .env
```

Edit `.env` and keep the runtime on Bedrock:

- `AI_PROVIDER=bedrock`
- `AWS_PROFILE`
- `AWS_REGION`
- one of `BEDROCK_INFERENCE_PROFILE_ID`, `BEDROCK_INFERENCE_PROFILE_ARN`, or `BEDROCK_MODEL_ID`

Recommended Bedrock example:

```dotenv
AI_PROVIDER=bedrock
AWS_REGION=us-east-1
AWS_PROFILE=TK-Admin
BEDROCK_INFERENCE_PROFILE_ARN=arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0
```

## Desktop App POC

The desktop app uses Electron for the cross-platform shell and React for the UI. Electron starts a local Python API that reuses the same `.env`, Bedrock client, and `ChatService` as the CLI. It also stores local chat sessions in SQLite so prior conversations can populate the sidebar.

Start the desktop app from the repo root:

```bash
make desktop-dev
```

Useful desktop targets:

- `make desktop-api`: run only the local Python API on `127.0.0.1:8765`
- `make desktop-build`: build the React renderer into `desktop/dist/`
- `make desktop-pack`: build React and create an unpacked Electron app directory

## Testing

Core local test commands from the repo root:

```bash
python3 -m unittest discover -s tests
npm run desktop:test
python3 -m compileall app tests
```

Useful narrower checks:

- `python3 -m unittest tests.test_server` for the local API server contract
- `python3 -m unittest tests.test_session_store tests.test_chat_service` for session persistence and context handling
- `npm run desktop:build` for the Electron/React renderer build

Local database details:

- packaged desktop default: Electron user-data directory, `assistant.db`
- desktop dev default: project-root `.local/assistant.db`
- standalone server default: `.local/assistant.db`
- override path: set `HYBRID_AI_DB_PATH` or pass `--db-path` to `python -m app.server`

Desktop dev builds automatically migrate the legacy Electron user-data database into the
project-local `.local/assistant.db` path the first time they see an older dev install.

The SQLite session store tracks schema state with `PRAGMA user_version`.

- first run initializes the current schema automatically
- older versionless databases migrate forward when opened
- current migrations preserve existing `sessions` and `messages` rows and add required indexes

For packaged desktop builds, the app expects a Python runtime and project environment to be available. Set `HYBRID_AI_PYTHON`, `HYBRID_AI_ENV_FILE`, or `HYBRID_AI_DB_PATH` when you need to point Electron at a non-default Python executable, env file, or SQLite database path.

## CDK Setup

Create the infra virtualenv and install CDK libraries:

```bash
make infra-bootstrap
```

Bootstrap the target AWS environment once:

```bash
AWS_PROFILE=TK-Admin AWS_REGION=us-east-1 ./scripts/bootstrap-cdk.sh
```

The bootstrap script:

- resolves the active account with `aws sts get-caller-identity`
- installs `infra/requirements.txt` into `infra/.venv`
- runs `cdk bootstrap` against that account and region

## Deploy The Baseline

Deploy the stack with the shared AWS profile and any optional config overrides:

```bash
AWS_PROFILE=TK-Admin AWS_REGION=us-east-1 \
BEDROCK_INFERENCE_PROFILE_ARNS=arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-sonnet-4-6 \
./scripts/deploy-baseline.sh
```

Only set `OPERATOR_USER_NAME` if that IAM user already exists in the target AWS account. Leave it unset to skip the optional developer operator role.

Useful deployment-time environment variables:

- `PROJECT_NAME`
- `ENVIRONMENT_NAME`
- `COMPANY_NAME`
- `ORGANIZATION_SEGMENT`
- `ASSETS_BUCKET_NAME_OVERRIDE`
- `ASSETS_BUCKET_FORCE_DESTROY`
- `LOG_RETENTION_DAYS`
- `BEDROCK_FOUNDATION_MODEL_IDS`
- `BEDROCK_INFERENCE_PROFILE_ARNS`
- `BEDROCK_GUARDRAIL_ARNS`
- `RUNTIME_TRUSTED_PRINCIPAL_ARNS`
- `OPERATOR_USER_NAME`
- `OPERATOR_ROLE_NAME_OVERRIDE`
- `OPERATOR_ROLE_ENABLE_OBSERVABILITY_ACCESS`

Comma-separated values are accepted for the Bedrock allow-lists and trusted principal ARNs.

## Copy Stack Outputs Into `.env`

After deploy, use CloudFormation outputs to wire local references:

```bash
AWS_PROFILE=TK-Admin AWS_REGION=us-east-1 \
aws cloudformation describe-stacks \
  --stack-name HybridAiPlatformBaseline \
  --query "Stacks[0].Outputs"
```

Typical mappings:

- `AiAssetsBucketName` -> `AI_ASSETS_BUCKET_NAME`
- `AssistantLogGroupName` -> `ASSISTANT_LOG_GROUP_NAME`
- `AwsRegion` -> `AWS_REGION`

If you enabled the operator role, its outputs are:

- `DeveloperOperatorRoleArn`
- `DeveloperOperatorRoleName`

## Daily Workflow

Local assistant:

```bash
.venv/bin/python -m app --prompt "Summarize the purpose of this hybrid AI platform."
```

Desktop assistant:

```bash
make desktop-dev
```

Infra validation:

```bash
make infra-test
make cdk-synth
```

Diff or redeploy:

```bash
make cdk-diff
make cdk-deploy
```

Smoke checks:

```bash
make smoke
make smoke-bedrock
make smoke-stack
```

Smoke target intent:

- `make smoke`: local static smoke for app tests, infra tests, and `cdk synth`
- `make smoke-bedrock`: live Bedrock invoke smoke using `.env`
- `make smoke-stack`: deployed stack verification against CloudFormation, S3, CloudWatch Logs, and IAM
- `make smoke-deploy`: deploy then run `make smoke-stack`

## Dev Strategy

This repo should use a `dev`-first Git strategy instead of treating ad hoc feature branches as the default working model.

The intended branch roles are:

- `main`: promoted, stable branch
- `dev`: active integration branch for ongoing platform work
- short-lived topic branches: optional, only when a change needs isolation before merging back into `dev`

The operating rule is:

1. land active development into `dev`
2. validate on `dev`
3. promote `dev` into `main` when the baseline is ready

For day-to-day work, prefer:

```bash
git switch dev
git pull origin dev
```

If a topic branch is useful for a risky or isolated change, branch from `dev` and merge back into `dev`, not directly into `main`.

## Repository Notes

- Existing Terraform state or module history in older clones should be treated as legacy material, not a deploy path.
- The Python assistant remains intentionally small; the CDK stack is the durable account baseline around it.
- Bedrock is the operating runtime for this repo.
- The Git integration branch should be `dev`.
- GitHub Actions now runs `make smoke` on `dev`, `main`, and pull requests. Manual workflow dispatch can also run live AWS smoke checks when the repo has the required AWS role and smoke variables configured.

## Related Docs

- [docs/architecture.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/architecture.md)
- [docs/bedrock-claude-notes.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/bedrock-claude-notes.md)
- [docs/kilo-code-setup.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/kilo-code-setup.md)
- [docs/dev-strategy.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/dev-strategy.md)
- [docs/operator-runbook.md](/Users/nathanmalitz/Code/hybrid-ai-platform/docs/operator-runbook.md)
