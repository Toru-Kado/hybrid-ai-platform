PYTHON ?= python3.12
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTHON_BIN := $(VENV)/bin/python

.PHONY: bootstrap install run example compile test verify terraform-init terraform-plan terraform-apply terraform-fmt tree

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e .

install:
	$(PIP) install -e .

run:
	$(PYTHON_BIN) -m app --prompt "Summarize the purpose of this hybrid AI platform."

example:
	$(PYTHON_BIN) -m app --system "You are a senior cloud architect." --prompt "Explain why Bedrock is the primary runtime in this repository."

compile:
	$(PYTHON_BIN) -m compileall app

test:
	$(PYTHON_BIN) -m unittest discover -s tests

verify: compile test

terraform-init:
	terraform -chdir=infra/environments/dev init

terraform-plan:
	terraform -chdir=infra/environments/dev plan

terraform-apply:
	terraform -chdir=infra/environments/dev apply

terraform-fmt:
	terraform fmt -recursive infra

tree:
	find . -path ./.git -prune -o -path ./.venv -prune -o -print | sort
