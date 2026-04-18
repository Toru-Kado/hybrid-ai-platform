# Architecture

## Goal

Provide a lightweight AI platform baseline where:

- the local machine stays focused on development and orchestration
- Amazon Bedrock remains the primary model runtime
- AWS CDK defines the infrastructure contract
- the AWS footprint lives in the Toru Kadu segment of the Angelica Technologies organization
- the Python assistant is the first operator-facing surface

## High-Level Design

```text
┌────────────────────────────┐
│ Local Workstation          │
│ - Python assistant CLI     │
│ - AWS CLI / profiles       │
│ - CDK CLI                  │
│ - editor workflows         │
└──────────────┬─────────────┘
               │
               │ HTTPS / AWS APIs
               ▼
┌──────────────────────────────────────────┐
│ AWS Account                             │
│ Toru Kadu organization segment          │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ Amazon Bedrock                     │  │
│  │ - Claude inference runtime         │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ S3                                 │  │
│  │ - AI assets                        │  │
│  │ - prompt archives                  │  │
│  │ - exports / eval data              │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ CloudWatch Logs                    │  │
│  │ - assistant runtime log group      │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ IAM Runtime / Operator Roles       │  │
│  │ - Bedrock invoke permissions       │  │
│  │ - S3 access                        │  │
│  │ - CloudWatch write access          │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Why This Shape

- The repo no longer needs Terraform-era module layering for a very small baseline.
- CDK aligns this repo with the newer precedent already in `fooocus-rig`.
- Bedrock keeps model execution in AWS while the laptop stays a control plane.
- The resource baseline is still intentionally small: durable storage, logs, and IAM boundaries first.

## Core Components

### 1. Local Workstation

- runs the assistant CLI
- runs AWS CLI and CDK commands
- owns `.env`, local profiles, and source code

### 2. Amazon Bedrock

- primary inference runtime
- selected through environment configuration
- supports direct model IDs or inference profiles

### 3. AI Assets Bucket

- prompt packs
- evaluation datasets
- conversation exports
- generated artifacts

### 4. Assistant Log Group

- stable log destination for future hosted runtimes
- shared operational namespace for assistant workloads

### 5. Runtime and Operator Roles

- runtime role for future AWS-hosted execution paths
- optional operator role for local human use
- policy scope can be narrowed to exact models, inference profiles, and guardrails

## Repository Mapping

- [app](/Users/nathanmalitz/Code/hybrid-ai-platform/app): Python assistant package
- [infra](/Users/nathanmalitz/Code/hybrid-ai-platform/infra): CDK app and assertion tests
- [scripts](/Users/nathanmalitz/Code/hybrid-ai-platform/scripts): bootstrap and deploy helpers
- [docs](/Users/nathanmalitz/Code/hybrid-ai-platform/docs): operating notes and architecture records

## Operational Flow

1. The operator authenticates to the intended Toru Kadu AWS account.
2. CDK bootstraps the account and synthesizes the baseline stack.
3. CDK deploys the S3 bucket, log group, and IAM roles.
4. The operator copies stack outputs into `.env` where useful.
5. The Python CLI invokes Claude through Amazon Bedrock.

## Extension Points

- add hosted execution on Lambda, ECS, or batch
- persist prompts and outputs to S3
- add more formal environment overlays if non-dev stacks become necessary
- introduce CI checks for both the app tests and CDK assertion tests
