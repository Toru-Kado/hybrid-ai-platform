# Kilo Code Setup

## Scope

This document keeps two things separate:

- AWS setup that must already exist
- editor settings that need to map onto that AWS setup

The repo does not manage Kilo Code config files directly.

## Required AWS Setup

Before configuring Kilo Code, you need:

1. an AWS profile that resolves to the intended Toru Kado account
2. a Bedrock-enabled region
3. access to a Claude model or inference profile in that region

Minimum checks:

```bash
aws sts get-caller-identity --profile TK-Admin
```

Use the same AWS values that you place in `.env` for the Python app:

- `AWS_PROFILE`
- `AWS_REGION`
- `BEDROCK_MODEL_ID` or the matching Bedrock selector in the editor

## Editor Configuration Assumptions

Map the editor configuration to these concepts:

- AI provider: Amazon Bedrock
- authentication source: your local AWS CLI credentials or named AWS profile
- region: the same region used in `.env`
- model: a Claude target enabled in the current account and region

If Kilo Code inherits shell environment variables, exporting them before launch is the simplest setup:

```bash
export AWS_PROFILE=TK-Admin
export AWS_REGION=us-east-1
```

If the editor does not inherit them, configure those same values inside the editor UI.

## Practical Recommendation

Keep Kilo Code aligned with the CLI:

- same AWS profile
- same AWS region
- same Claude target when possible

That avoids debugging one tool against a different Bedrock account or region than the other.

## Common Failure Modes

### Access denied

- Bedrock access is not enabled for the current account, region, or model
- the editor is using different credentials than your shell
- the active account is not the intended Toru Kado target

### Wrong region

- the editor points at a different region than `.env`
- the Claude target is enabled in another region

### Drift between tools

- Kilo Code uses one model while the Python app uses another
- the CLI uses one AWS profile while the editor uses another
