# Multi-Environment CDK Deployment

This document describes the multi-environment CDK setup for deploying the hybrid AI platform to different AWS environments (dev, staging, prod).

## Architecture

The CDK infrastructure uses a single stack definition (`HybridAiPlatformBaselineStack`) with environment-specific configurations. Configuration is driven by environment variables, with sensible defaults for each environment type.

### Environment Presets

Each environment has automatic defaults that can be overridden:

| Setting | Dev | Staging | Prod |
|---------|-----|---------|------|
| **Bucket Force Destroy** | ✓ (allow delete) | ✗ (retain) | ✗ (retain) |
| **Log Retention** | 7 days | 30 days | 90 days |
| **Operator Access** | Enabled | Enabled | Disabled |
| **Cost Profile** | Low | Medium | High |

### Stack Resources

Each environment stack creates:

1. **S3 Assets Bucket** — Versioned, encrypted, private storage for AI model assets
2. **CloudWatch Log Group** — Structured logging for assistant activity
3. **IAM Roles**
   - **Runtime Role**: Used by compute services to invoke Bedrock
   - **Operator Role** (optional): Used by development/operations staff

## Deployment Workflow

### 1. Choose Environment

Set `ENVIRONMENT_TYPE`:

```bash
# Development
export ENVIRONMENT_TYPE=dev

# Staging
export ENVIRONMENT_TYPE=staging

# Production
export ENVIRONMENT_TYPE=prod
```

### 2. Load Environment Config

Source the environment-specific file:

```bash
source infra/.env.${ENVIRONMENT_TYPE}
```

Or manually set required variables:

```bash
export AWS_REGION=us-east-1
export AWS_PROFILE=TK-Admin
export CDK_DEFAULT_REGION=us-east-1
```

### 3. Verify Changes (Optional)

Review what will be deployed:

```bash
# View CDK diff for the target environment
make cdk-diff-${ENVIRONMENT_TYPE}

# Example for prod
make cdk-diff-prod
```

### 4. Deploy

```bash
# Deploy to the target environment
make cdk-deploy-${ENVIRONMENT_TYPE}

# Example
make cdk-deploy-prod
```

Or use the deploy script directly:

```bash
ENVIRONMENT_TYPE=prod ./scripts/deploy-baseline.sh
```

## Configuration Reference

### Environment Variables

All configuration is environment-driven via `.env.{dev,staging,prod}`:

```bash
# Environment selection (required)
ENVIRONMENT_TYPE=dev|staging|prod
ENVIRONMENT_NAME=dev                    # Custom label (defaults to ENVIRONMENT_TYPE)

# Project metadata
PROJECT_NAME=hybrid-ai-platform
COMPANY_NAME=Toru Kado
ORGANIZATION_SEGMENT=toru-kado

# AWS
AWS_REGION=us-east-1
AWS_PROFILE=TK-Admin
CDK_DEFAULT_REGION=us-east-1

# Logging
LOG_RETENTION_DAYS=7|30|90              # Auto-set by environment, can override

# Storage
ASSETS_BUCKET_NAME_OVERRIDE=            # Custom bucket name (optional)
ASSETS_BUCKET_FORCE_DESTROY=true|false  # Auto-set by environment, can override

# Bedrock configuration
BEDROCK_FOUNDATION_MODEL_IDS=           # Comma-separated, direct model IDs
BEDROCK_INFERENCE_PROFILE_ARNS=         # Comma-separated, inference profile ARNs
BEDROCK_GUARDRAIL_ARNS=                 # Comma-separated, guardrail ARNs

# Runtime access
RUNTIME_TRUSTED_PRINCIPAL_ARNS=         # Comma-separated, cross-account/service ARNs

# Operator role (optional)
OPERATOR_USER_NAME=                     # IAM username for local dev access
OPERATOR_ROLE_ENABLE_OBSERVABILITY_ACCESS=true|false
```

## Common Tasks

### Deploy Dev Environment

```bash
source infra/.env.dev
make cdk-deploy-dev
```

### Prepare Prod Deployment

```bash
source infra/.env.prod
make cdk-diff-prod
# Review output, then deploy when confident
make cdk-deploy-prod
```

### Promote Staging to Prod

```bash
# Review staging stack
source infra/.env.staging
make cdk-diff-staging

# When ready, deploy prod
source infra/.env.prod
make cdk-deploy-prod
```

### Configure Bedrock Access

For production, update `.env.prod` with your Bedrock configuration:

```bash
# Use inference profiles for cross-region resilience (recommended for prod)
BEDROCK_INFERENCE_PROFILE_ARNS=arn:aws:bedrock:us-east-1:123456789:inference-profile/my-profile

# Or use direct model IDs (single region)
BEDROCK_FOUNDATION_MODEL_IDS=anthropic.claude-3-5-sonnet-20241022-v2:0

# Optional: enable guardrails
BEDROCK_GUARDRAIL_ARNS=arn:aws:bedrock:us-east-1:123456789:guardrail/my-guardrail
```

### Add Cross-Account Access

To allow another AWS account or service to use the runtime role:

```bash
# In .env.{environment}
RUNTIME_TRUSTED_PRINCIPAL_ARNS=arn:aws:iam::OTHER-ACCOUNT:role/other-role,arn:aws:iam::THIS-ACCOUNT:role/service-role
```

## Outputs

After deployment, CDK outputs key resource identifiers:

```
AiAssetsBucketName              s3 bucket name for assets
AssistantLogGroupName           CloudWatch log group for logs
AssistantRuntimeRoleArn         IAM role for Bedrock invocation
DeveloperOperatorRoleName       (optional) role for operators
```

Capture and use these in your application configuration:

```bash
# After deployment, add to your app .env
AI_ASSETS_BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name HybridAiPlatformBaseline \
  --query 'Stacks[0].Outputs[?OutputKey==`AiAssetsBucketName`].OutputValue' \
  --output text)
```

## Best Practices

### Development (`dev`)
- ✓ Use local AWS profile
- ✓ Enable force-destroy for quick iteration
- ✓ Shorter log retention (saves costs)
- ✓ Operator role for debugging

### Staging (`staging`)
- ✓ Protect data (force-destroy=false)
- ✓ Moderate log retention (30 days)
- ✓ Test Bedrock guardrails
- ✓ Mirror prod settings where possible

### Production (`prod`)
- ✓ Long log retention (90+ days)
- ✓ Use inference profiles (cross-region)
- ✓ Enable guardrails
- ✓ Disable operator role (use IAM policies)
- ✓ Immutable bucket policy
- ✓ Review `cdk diff` before every deploy
- ⚠️ Never set `ASSETS_BUCKET_FORCE_DESTROY=true`

## Troubleshooting

### "Configuration error: ENVIRONMENT_TYPE must be one of: dev, staging, prod"

Set `ENVIRONMENT_TYPE` before deploying:

```bash
export ENVIRONMENT_TYPE=prod
```

### "Environment file not found"

Ensure you're in the repo root and the env file exists:

```bash
ls infra/.env.${ENVIRONMENT_TYPE}
```

### "OPERATOR_USER_NAME does not exist"

Either:
1. Unset `OPERATOR_USER_NAME` (optional feature)
2. Set it to an existing IAM user in your account

### CloudFormation drift after manual changes

CDK tracks the source of truth. Avoid manual changes to stacks. To reset:

```bash
make cdk-diff-prod
# Review, then redeploy
make cdk-deploy-prod
```

## Next Steps

After the baseline stack is deployed, you can:

1. **Add compute** — API Gateway + Lambda/App Runner for the Python server
2. **Add data layer** — RDS/DynamoDB for persistent session storage
3. **Enable monitoring** — X-Ray tracing, CloudWatch alarms, Cost Explorer
4. **Secure further** — VPC, private endpoints, WAF, KMS encryption

See `docs/architecture.md` for the full modernization roadmap.
