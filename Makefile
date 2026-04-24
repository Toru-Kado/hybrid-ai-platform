PYTHON ?= $(shell command -v python3.12 || command -v python3.14 || command -v python3.13 || command -v python3)
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTHON_BIN := $(VENV)/bin/python
INFRA_VENV ?= infra/.venv
INFRA_PIP := $(INFRA_VENV)/bin/pip
INFRA_PYTHON := $(INFRA_VENV)/bin/python
JSII_RUNTIME_PACKAGE_CACHE_ROOT ?= $(CURDIR)/.cache/jsii

export JSII_RUNTIME_PACKAGE_CACHE_ROOT

.PHONY: check-python bootstrap install run example compile test verify frontend-bootstrap desktop-api desktop-dev desktop-build desktop-pack infra-bootstrap infra-test cdk-bootstrap cdk-synth cdk-diff cdk-deploy smoke smoke-local smoke-bedrock smoke-stack smoke-deploy tree

check-python:
	$(PYTHON) -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 'Python >= 3.12 required; set PYTHON=/path/to/python3.12+')"

bootstrap: check-python
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .

install:
	$(PIP) install -e .

run:
	$(PYTHON_BIN) -m app --prompt "Summarize the purpose of this hybrid AI platform."

example:
	$(PYTHON_BIN) -m app --system "You are a pragmatic cloud architect." --prompt "Explain why this repository keeps Bedrock as the primary runtime."

frontend-bootstrap:
	npm install

desktop-api:
	$(PYTHON_BIN) -m app.server

desktop-dev:
	npm run desktop:dev

desktop-build:
	npm run desktop:build

desktop-pack:
	npm run desktop:pack

compile:
	$(PYTHON_BIN) -m compileall app

test:
	$(PYTHON_BIN) -m unittest discover -s tests

verify: compile test

infra-bootstrap: check-python
	$(PYTHON) -m venv $(INFRA_VENV)
	$(INFRA_PIP) install --upgrade pip
	$(INFRA_PIP) install -r infra/requirements.txt

infra-test:
	cd infra && .venv/bin/python -m pytest tests

smoke: smoke-local

smoke-local: verify infra-test cdk-synth

smoke-bedrock:
	$(PYTHON_BIN) scripts/smoke.py bedrock --env-file .env

smoke-stack:
	$(PYTHON_BIN) scripts/smoke.py stack --env-file .env

smoke-deploy:
	$(PYTHON_BIN) scripts/smoke.py deploy --env-file .env

cdk-bootstrap:
	./scripts/bootstrap-cdk.sh

cdk-synth:
	cd infra && cdk synth

cdk-diff:
	cd infra && cdk diff

cdk-deploy:
	./scripts/deploy-baseline.sh

tree:
	find . -path ./.git -prune -o -path ./.venv -prune -o -path ./infra/.venv -prune -o -print | sort
