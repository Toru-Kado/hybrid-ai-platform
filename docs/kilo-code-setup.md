# Kilo Code Setup

## Objective

Configure Kilo Code to use AWS Bedrock as its AI backend so the same cloud runtime is shared across:

- Local assistant CLI usage
- Kilo Code-assisted development
- Future hosted assistant components

## Recommended Setup Pattern

Use one AWS profile and one primary Bedrock region for all local tools:

- `AWS_PROFILE=hybrid-ai-dev`
- `AWS_REGION=us-east-1`
- `BEDROCK_MODEL_ID=<approved Claude model ID>`

That keeps Kilo Code and the Python app aligned.

## Local Credential Preparation

1. Install AWS CLI v2.
2. Configure a local profile.
3. Confirm STS works for the selected profile.

```bash
aws configure --profile hybrid-ai-dev
aws sts get-caller-identity --profile hybrid-ai-dev
```

If you intend to assume the Terraform-created runtime role, wire that into your AWS CLI config rather than hard-coding temporary credentials in tool settings.

## Kilo Code Configuration Guidance

Exact labels in Kilo Code can change by version, so keep the configuration aligned to these concepts:

- Provider: `AWS Bedrock`
- Authentication source: local AWS credentials or named profile
- Region: the Bedrock-enabled AWS region you chose in Terraform and `.env`
- Model: a Claude model enabled in your account

Recommended order:

1. Set the AWS profile in your shell environment before launching Kilo Code.
2. Point Kilo Code at the same region used by the Python app.
3. Select the same Claude model family used for assistant experiments.

## Practical Workflow

- Use the Python CLI for quick smoke tests against Bedrock.
- Use Kilo Code for coding assistance backed by the same AWS identity.
- Keep Bedrock model changes centralized in your `.env` and local tool config.

## Suggested Local Launch Pattern

```bash
export AWS_PROFILE=hybrid-ai-dev
export AWS_REGION=us-east-1
open /Applications/Kilo\ Code.app
```

If Kilo Code reads environment variables on launch, this is usually the cleanest approach.

## Common Failure Modes

## Access denied

- Bedrock access is not enabled for the account, region, or model
- The AWS profile lacks `bedrock:InvokeModel` or `bedrock:Converse`
- The runtime role trust relationship is too narrow for the local identity

## Wrong region

- The CLI and Kilo Code point at different regions
- The chosen Claude model is not enabled in the configured region

## Drift between tools

- Kilo Code uses one model while `.env` references another
- One tool uses direct credentials while another uses an assumed role

## Recommendation

Treat Kilo Code as another Bedrock client in the same platform, not as a separate setup. Reuse the same profile, region, and model decisions where possible.
