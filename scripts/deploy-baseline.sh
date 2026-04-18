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

cd "${INFRA_DIR}"
cdk deploy "${STACK_NAME}" --require-approval never
