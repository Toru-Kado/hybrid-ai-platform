# Operator Runbook

This is the operator path for:

- bootstrapping the CDK environment
- deploying the baseline stack
- validating the CloudFormation outputs
- destroying or re-deploying the baseline later

## Git Baseline

Use `dev` as the active branch for ongoing platform work.

`main` should track promoted, stable states. If you are preparing or validating infrastructure changes, start from `dev` unless you are doing a release promotion.

## Prerequisites

You need:

- AWS CLI configured with credentials that can deploy CDK stacks
- Node.js and the AWS CDK CLI installed locally
- Python 3 available locally
- access to the intended Toru Kado AWS account

If you are using AWS IAM Identity Center:

- use the profile that resolves to the intended Toru Kado account
- verify the active account with `aws sts get-caller-identity --profile TK-Admin`

## First-Time Local Setup

Create the app and infra environments:

```bash
make bootstrap
make infra-bootstrap
```

If the AWS environment has not been bootstrapped for CDK yet:

```bash
AWS_PROFILE=TK-Admin AWS_REGION=us-east-1 ./scripts/bootstrap-cdk.sh
```

## Deploy The Baseline

From the repo root:

```bash
AWS_PROFILE=TK-Admin AWS_REGION=us-east-1 ./scripts/deploy-baseline.sh
```

Optional deploy-time controls are supplied through environment variables such as:

- `BEDROCK_FOUNDATION_MODEL_IDS`
- `BEDROCK_INFERENCE_PROFILE_ARNS`
- `BEDROCK_GUARDRAIL_ARNS`
- `RUNTIME_TRUSTED_PRINCIPAL_ARNS`
- `OPERATOR_USER_NAME`
- `ASSETS_BUCKET_NAME_OVERRIDE`

## Validate Outputs

Inspect the deployed stack outputs:

```bash
AWS_PROFILE=TK-Admin AWS_REGION=us-east-1 \
aws cloudformation describe-stacks \
  --stack-name HybridAiPlatformBaseline \
  --query "Stacks[0].Outputs"
```

Use those outputs to populate local references in `.env`.

## Smoke Checks

Use the smoke targets to separate local validation from live AWS validation:

```bash
make smoke
make smoke-bedrock
make smoke-stack
```

Use `make smoke` before opening a PR. Use `make smoke-bedrock` after changing local Bedrock auth or model targeting. Use `make smoke-stack` after a deploy when you need to confirm the baseline bucket, log group, and IAM roles exist in the target account.

## Diff Or Re-Synth

```bash
make cdk-synth
make cdk-diff
```

## Destroy

Destroy only if the environment is disposable and the S3 bucket is empty or was created with `ASSETS_BUCKET_FORCE_DESTROY=true`.

```bash
cd infra
source .venv/bin/activate
cdk destroy HybridAiPlatformBaseline
```
