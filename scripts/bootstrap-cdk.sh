#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="${ROOT_DIR}/infra"

AWS_PROFILE="${AWS_PROFILE:-TK-Admin}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="$(
  aws sts get-caller-identity \
    --profile "${AWS_PROFILE}" \
    --query Account \
    --output text
)"

cd "${INFRA_DIR}"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

export AWS_PROFILE
export AWS_REGION

cdk bootstrap "aws://${ACCOUNT_ID}/${AWS_REGION}"
