#!/usr/bin/env bash
set -euo pipefail

# Build and deploy the React SPA to S3 + invalidate CloudFront.
# Usage: ./scripts/deploy-frontend.sh [dev|staging|prod]
#
# Prerequisites:
#   - Node.js and npm installed
#   - AWS credentials configured
#   - Serverless stack deployed (provides S3 bucket and CloudFront distribution)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

ENV="${1:-${ENVIRONMENT_TYPE:-dev}}"
export ENVIRONMENT_TYPE="$ENV"

echo "=== Deploying frontend (environment: $ENV) ==="

# Read outputs from CDK deployment
OUTPUTS_FILE="$PROJECT_ROOT/.cdk-outputs-serverless-$ENV.json"
if [ ! -f "$OUTPUTS_FILE" ]; then
    echo "ERROR: CDK outputs file not found: $OUTPUTS_FILE"
    echo "Deploy the serverless stack first: make cdk-deploy-serverless-$ENV"
    exit 1
fi

SPA_BUCKET=$(python3 -c "
import json
with open('$OUTPUTS_FILE') as f:
    outputs = json.load(f)
print(outputs['HybridAiPlatformServerless']['SpaBucketName'])
")

DISTRIBUTION_ID=$(python3 -c "
import json
with open('$OUTPUTS_FILE') as f:
    outputs = json.load(f)
# CloudFront distribution ID is extracted from the URL or we need to look it up
url = outputs['HybridAiPlatformServerless']['CloudFrontDistributionUrl']
print(url)
" 2>/dev/null || echo "")

echo "Target S3 bucket: $SPA_BUCKET"

# Build the frontend
cd "$PROJECT_ROOT"
echo "Building React SPA (web mode)..."
npm run web:build

# Sync to S3
BUILD_DIR="$PROJECT_ROOT/dist/web"
if [ ! -d "$BUILD_DIR" ]; then
    echo "ERROR: Build output not found at $BUILD_DIR"
    exit 1
fi

echo "Syncing to S3..."
aws s3 sync "$BUILD_DIR" "s3://$SPA_BUCKET" \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --exclude "index.html" \
    --exclude "*.json"

# Upload index.html and manifests with no-cache
aws s3 cp "$BUILD_DIR/index.html" "s3://$SPA_BUCKET/index.html" \
    --cache-control "no-cache, no-store, must-revalidate"

# Upload any JSON files (manifests) with short cache
for json_file in "$BUILD_DIR"/*.json; do
    if [ -f "$json_file" ]; then
        aws s3 cp "$json_file" "s3://$SPA_BUCKET/$(basename "$json_file")" \
            --cache-control "public, max-age=60"
    fi
done

echo "Frontend deployed to s3://$SPA_BUCKET"

# Invalidate CloudFront cache
echo "Invalidating CloudFront cache..."
# Look up distribution ID by the SPA bucket origin
DIST_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[?DomainName=='${SPA_BUCKET}.s3.amazonaws.com']].Id | [0]" \
    --output text 2>/dev/null || echo "")

if [ -n "$DIST_ID" ] && [ "$DIST_ID" != "None" ]; then
    aws cloudfront create-invalidation \
        --distribution-id "$DIST_ID" \
        --paths "/*" \
        --output text > /dev/null
    echo "CloudFront invalidation created for distribution: $DIST_ID"
else
    echo "WARNING: Could not find CloudFront distribution to invalidate."
    echo "You may need to manually invalidate the cache."
fi

echo ""
echo "=== Frontend deployment complete ==="
