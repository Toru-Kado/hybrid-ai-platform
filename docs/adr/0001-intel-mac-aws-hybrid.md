# ADR 0001: Use the Local Workstation for Development and AWS Bedrock With a CDK Baseline

## Status

Accepted

## Date

2026-04-17

## Context

The platform is intended for a solo operator working locally while targeting AWS for AI execution.

The original repo shape leaned on Terraform and an earlier AWS account path. That is no longer the operating model.

Current constraints:

- the local machine should remain a development and orchestration box
- Amazon Bedrock is still the preferred runtime
- infrastructure should align with the CDK-first precedent already used in `fooocus-rig`
- deployments should target the Toru Kado AWS organization segment
- the solution should stay understandable and easy to evolve

## Decision

Use the local workstation as the control plane for:

- source code development
- local Python assistant usage
- AWS CLI and profile-based authentication
- CDK bootstrap, synth, diff, and deploy workflows

Use AWS as the execution environment for AI capabilities:

- Amazon Bedrock for Claude inference
- S3 for AI-related assets
- CloudWatch Logs for operational visibility
- IAM runtime and operator roles for access boundaries

Use AWS CDK, not Terraform, as the IaC source of truth for the platform baseline.

## Rationale

- it aligns this repo with the newer infrastructure direction already in use elsewhere
- it removes Terraform-era scaffolding that no longer matches the target account model
- it keeps the deployable baseline small while still giving the repo a durable AWS footprint
- it preserves a clean path to Lambda, ECS, or other hosted workloads later

## Consequences

Positive:

- one AWS IaC approach across related repos
- simpler bootstrap and deploy workflow for this repo
- clearer alignment with the intended AWS org/account path
- easier testing of infrastructure intent through CDK assertions

Negative:

- operators now need local CDK CLI setup in addition to the AWS CLI
- older Terraform state and tfvars are no longer meaningful deploy artifacts
- account verification matters more because the same operator profile may reach multiple AWS accounts

## Alternatives Considered

## 1. Keep Terraform and only update account references

Rejected because:

- it preserves the wrong infrastructure workflow for the new direction
- it keeps legacy module structure that is no longer buying much for this repo

## 2. Remove infrastructure from this repo entirely

Rejected because:

- the repo still benefits from owning its baseline bucket, logs, and IAM roles
- Bedrock-focused workflows still need a durable AWS boundary

## 3. Move directly to a larger hosted platform design

Rejected because:

- the repo still benefits from a small baseline first
- heavier orchestration layers are premature until the assistant outgrows the CLI

## Follow-On Decisions

- add more explicit non-dev environment strategy only when needed
- narrow Bedrock resource allow-lists once the target models and profiles settle
- add CI coverage for both app tests and CDK assertion tests
