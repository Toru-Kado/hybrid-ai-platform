PYTHON ?= python3.12
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTHON_BIN := $(VENV)/bin/python
INFRA_VENV ?= infra/.venv
INFRA_PIP := $(INFRA_VENV)/bin/pip
INFRA_PYTHON := $(INFRA_VENV)/bin/python

.PHONY: bootstrap install run example compile test verify infra-bootstrap infra-test cdk-bootstrap cdk-synth cdk-diff cdk-deploy tree

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .

install:
	$(PIP) install -e .

run:
	$(PYTHON_BIN) -m app --prompt "Summarize the purpose of this hybrid AI platform."

example:
	$(PYTHON_BIN) -m app --system "You are a pragmatic cloud architect." --prompt "Explain why this repository keeps Bedrock as the primary runtime."

compile:
	$(PYTHON_BIN) -m compileall app

test:
	$(PYTHON_BIN) -m unittest discover -s tests

verify: compile test

infra-bootstrap:
	$(PYTHON) -m venv $(INFRA_VENV)
	$(INFRA_PIP) install --upgrade pip
	$(INFRA_PIP) install -r infra/requirements.txt

infra-test:
	cd infra && .venv/bin/python -m pytest tests

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
