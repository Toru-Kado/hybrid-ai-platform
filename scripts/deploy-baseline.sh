#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${ROOT_DIR}/infra"

AWS_PROFILE="${AWS_PROFILE:-TK-Admin}"
AWS_REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${STACK_NAME:-HybridAiPlatformBaseline}"

if [[ ! -x "${INFRA_DIR}/.venv/bin/python" ]]; then
  echo "infra/.venv is missing. Run ./scripts/bootstrap-cdk.sh first." >&2
  exit 1
fi

export AWS_PROFILE
export AWS_REGION

if [[ -n "${OPERATOR_USER_NAME:-}" ]]; then
  if ! aws iam get-user --user-name "${OPERATOR_USER_NAME}" >/dev/null 2>&1; then
    cat >&2 <<EOF
OPERATOR_USER_NAME is set to '${OPERATOR_USER_NAME}', but that IAM user does not exist in the target account.
Unset OPERATOR_USER_NAME to skip the optional developer operator role, or set it to an existing IAM user.
EOF
    exit 1
  fi
fi

cd "${INFRA_DIR}"
cdk deploy "${STACK_NAME}" --require-approval never
