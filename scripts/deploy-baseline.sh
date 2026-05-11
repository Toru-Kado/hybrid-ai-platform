#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${ROOT_DIR}/infra"

# Default environment is dev
ENVIRONMENT_TYPE="${ENVIRONMENT_TYPE:-dev}"
AWS_PROFILE="${AWS_PROFILE:-TK-Admin}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-HybridAiPlatformBaseline}"

# Validate environment
if [[ ! "$ENVIRONMENT_TYPE" =~ ^(dev|staging|prod)$ ]]; then
  echo "Error: ENVIRONMENT_TYPE must be dev, staging, or prod (got: $ENVIRONMENT_TYPE)" >&2
  exit 1
fi

# Load environment-specific config
ENV_FILE="${INFRA_DIR}/.env.${ENVIRONMENT_TYPE}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: Environment file not found: $ENV_FILE" >&2
  exit 1
fi

# Source environment config
set +u
source "$ENV_FILE"
set -u

# Verify infra venv
if [[ ! -x "${INFRA_DIR}/.venv/bin/python" ]]; then
  echo "infra/.venv is missing. Run ./scripts/bootstrap-cdk.sh first." >&2
  exit 1
fi

# Verify operator user exists (if configured)
if [[ -n "${OPERATOR_USER_NAME:-}" ]]; then
  if ! aws iam get-user --user-name "${OPERATOR_USER_NAME}" >/dev/null 2>&1; then
    cat >&2 <<EOF
OPERATOR_USER_NAME is set to '${OPERATOR_USER_NAME}', but that IAM user does not exist.
Unset OPERATOR_USER_NAME to skip the optional developer operator role, or set it to an existing IAM user.
EOF
    exit 1
  fi
fi

echo "================================"
echo "Deploying to: $ENVIRONMENT_TYPE"
echo "Stack: $STACK_NAME"
echo "Region: ${AWS_REGION}"
echo "Profile: ${AWS_PROFILE}"
echo "================================"

cd "${INFRA_DIR}"
cdk deploy "${STACK_NAME}" --require-approval never

