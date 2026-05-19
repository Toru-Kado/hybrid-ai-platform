#!/usr/bin/env bash
set -euo pipefail

# Deploy the serverless stack for a given environment.
# Usage: ./scripts/deploy-serverless.sh [dev|staging|prod]
#
# Prerequisites:
#   - AWS credentials configured
#   - CDK bootstrapped in target account/region
#   - Lambda layer packaged (make lambda-package)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ENV="${1:-${ENVIRONMENT_TYPE:-dev}}"
export ENVIRONMENT_TYPE="$ENV"

echo "=== Deploying serverless stack (environment: $ENV) ==="

# Load environment-specific config if available
ENV_FILE="$PROJECT_ROOT/.env.$ENV"
if [ -f "$ENV_FILE" ]; then
    echo "Loading config from $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
fi

# Package Lambda layer if not already done
LAYER_DIR="$PROJECT_ROOT/infra/lambda-layer/python"
if [ ! -d "$LAYER_DIR/app" ]; then
    echo "Packaging Lambda layer..."
    python3 "$PROJECT_ROOT/scripts/package-lambda.py"
fi

# Synthesize and deploy
cd "$PROJECT_ROOT/infra"

echo "Synthesizing CloudFormation template..."
cdk synth HybridAiPlatformServerless --quiet

echo "Deploying stack..."
cdk deploy HybridAiPlatformServerless \
    --require-approval never \
    --outputs-file "$PROJECT_ROOT/.cdk-outputs-serverless-$ENV.json"

echo ""
echo "=== Deployment complete ==="
echo "Outputs saved to .cdk-outputs-serverless-$ENV.json"

# Display key outputs
if [ -f "$PROJECT_ROOT/.cdk-outputs-serverless-$ENV.json" ]; then
    echo ""
    echo "Key endpoints:"
    python3 -c "
import json, sys
with open('$PROJECT_ROOT/.cdk-outputs-serverless-$ENV.json') as f:
    outputs = json.load(f)
stack = outputs.get('HybridAiPlatformServerless', {})
for key in ['CloudFrontDistributionUrl', 'HttpApiUrl', 'UserPoolId', 'UserPoolClientId']:
    if key in stack:
        print(f'  {key}: {stack[key]}')
" 2>/dev/null || true
fi
