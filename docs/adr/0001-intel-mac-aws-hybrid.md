# ADR 0001: Use an Intel Mac for Development and AWS Bedrock for AI Runtime

## Status

Accepted

## Date

2026-03-27

## Context

The platform is intended for a solo developer working on an Intel Core i9 MacBook Pro.

Constraints:

- The machine is not Apple Silicon
- Local heavy model inference is not a goal
- AWS is the primary cloud environment
- Anthropic Claude through Amazon Bedrock is the preferred runtime
- The solution should stay understandable and extensible

## Decision

Use the Intel MacBook Pro as the control plane for:

- Source code development
- Terraform execution
- Local Python assistant usage
- Kilo Code workflows

Use AWS as the execution environment for AI capabilities:

- Amazon Bedrock for Claude inference
- S3 for AI-related artifacts
- CloudWatch Logs for operational visibility
- IAM role boundaries for runtime access

## Rationale

- It avoids forcing local inference optimizations onto hardware that is better suited for development than model serving.
- It aligns local development with the eventual hosted runtime model.
- It reduces operational surface area compared with self-hosted GPU services.
- It keeps the first version small enough for a solo developer to operate confidently.

## Consequences

Positive:

- Low local complexity
- Clear security and access boundaries
- Easy migration path to Lambda, ECS, or other AWS runtimes
- Consistent AI provider interface for both CLI and editor tooling

Negative:

- Inference depends on AWS connectivity and Bedrock availability
- Cost is usage-based rather than fixed local compute
- Regional model availability must be managed explicitly

## Alternatives Considered

## 1. Run local open-weight models on the Intel Mac

Rejected because:

- It does not fit the hardware well for sustained heavy inference
- It adds operational complexity without helping the target cloud architecture

## 2. Build a more elaborate AWS platform immediately

Rejected because:

- VPCs, containers, and orchestration layers are not yet necessary
- It would slow down the solo developer with premature infrastructure decisions

## 3. Use a third-party hosted AI API directly from the laptop

Rejected because:

- Bedrock is the intended control surface
- IAM and AWS-native governance are part of the desired operating model

## Follow-On Decisions

- Add remote Terraform state when collaboration or CI becomes necessary
- Add hosted execution only when the assistant outgrows a local CLI
- Revisit guardrails and observability depth once real workloads exist
