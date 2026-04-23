# Dev Strategy

## Goal

Use `dev` as the repository's integration branch.

This repo is in active rework, so the branch model should optimize for iterative platform changes rather than pretending `main` is where unfinished work belongs.

## Branch Roles

- `main`: stable branch for promoted changes
- `dev`: default branch for active development and integration
- topic branches: optional short-lived branches created from `dev` when a change needs isolation

## Rules

1. branch new work from `dev` when a separate branch is needed
2. merge completed work back into `dev`
3. validate infrastructure and app behavior on `dev`
4. promote `dev` to `main` only when the current baseline is coherent and deployable

## Practical Workflow

For direct development on the integration branch:

```bash
git switch dev
git pull origin dev
```

For isolated changes:

```bash
git switch dev
git pull origin dev
git switch -c <topic-name>
```

Then merge the topic branch back into `dev`.

## Why This Fits This Repo

- the platform baseline is still changing materially
- CDK, AWS account assumptions, and runtime conventions are still being reset
- `dev` gives the repo a stable integration target without forcing every incomplete change toward `main`

## Promotion Rule

Promote `dev` to `main` after:

- app tests pass
- CDK assertions pass
- the stack synthesizes cleanly
- the AWS deployment path reflects the current intended account and Bedrock runtime model
