# Kilo Code Setup

## Scope

This document keeps two things separate:

- AWS setup that must already exist
- Assumptions you may need to map onto Kilo Code's current UI

The repository does not manage Kilo Code settings files. Treat this as operator guidance, not a generated editor config.

## Required AWS Setup

Before configuring Kilo Code, you need:

1. AWS CLI credentials that work locally
2. A Bedrock-enabled region
3. Access to a Claude model in that region

Minimum checks:

```bash
aws configure --profile hybrid-ai-dev
aws sts get-caller-identity --profile hybrid-ai-dev
```

Use the same values you place in `.env` for the Python app:

- `AWS_PROFILE`
- `AWS_REGION`
- `BEDROCK_MODEL_ID` or the equivalent model selector in the editor

## Editor Configuration Assumptions

Kilo Code versions may label settings differently. Do not assume exact field names from this document.

Map the editor configuration to these concepts:

- AI provider: Amazon Bedrock
- Authentication source: your local AWS credentials or named AWS profile
- Region: the same region used in `.env`
- Model: a Claude model enabled in your account and region

If Kilo Code inherits shell environment variables, exporting them before launch is the simplest setup:

```bash
export AWS_PROFILE=hybrid-ai-dev
export AWS_REGION=us-east-1
```

If Kilo Code does not inherit environment variables, configure the same values directly in the editor's AWS or Bedrock settings if those options exist.

## Practical Recommendation

Keep Kilo Code aligned with the CLI:

- Same AWS profile
- Same AWS region
- Same Claude model family when possible

That avoids debugging one tool with a different Bedrock configuration than the other.

## Common Failure Modes

### Access denied

- Bedrock access is not enabled for the account, region, or model
- The local AWS identity does not have Bedrock invoke permissions
- The editor is using different credentials than your shell

### Wrong region

- The editor points at a different region than `.env`
- The Claude model is enabled in a different region than the one configured locally

### Drift between tools

- Kilo Code uses one model while the Python app uses another
- The CLI uses `AWS_PROFILE` while the editor uses a different credential source
