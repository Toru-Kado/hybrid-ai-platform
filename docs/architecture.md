# Architecture

## Goal

Provide a lightweight hybrid AI development environment where:

- The Intel Core i9 MacBook Pro remains a developer workstation, not a model-serving box
- AWS provides the durable control plane and runtime services
- Anthropic Claude through Amazon Bedrock is the primary model execution path
- Terraform defines the initial platform baseline
- A small Python service acts as the first assistant interface

## High-Level Design

```text
┌────────────────────────────┐
│ Intel Core i9 MacBook Pro  │
│ - Terraform CLI            │
│ - Python assistant CLI     │
│ - Kilo Code                │
│ - AWS CLI / profiles       │
└──────────────┬─────────────┘
               │
               │ HTTPS / AWS APIs
               ▼
┌──────────────────────────────────────────┐
│ AWS Account                              │
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
│  │ IAM Runtime Role                   │  │
│  │ - Bedrock invoke permissions       │  │
│  │ - S3 access                        │  │
│  │ - CloudWatch write access          │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Why This Shape

- The laptop is strong enough for development, but not the right place to optimize for heavy local inference.
- Bedrock shifts model lifecycle, scaling, and secure API access into AWS.
- Terraform gives the solo developer a repeatable baseline without introducing multi-account or networking complexity too early.
- The Python app is small enough to understand in one sitting, but already structured for future API, worker, or hosted runtime expansion.

## Core Components

### 1. Local Workstation

- Runs Terraform and the Python CLI assistant
- Holds source code, `.env`, and local AWS profiles
- Can run Kilo Code against the same AWS account and Bedrock region

### 2. Amazon Bedrock

- Primary inference runtime
- Keeps local compute requirements low
- Allows model swaps by configuration rather than app rewrites

### 3. S3 AI Assets Bucket

Current use cases:

- Prompt packs
- Evaluation datasets
- Conversation exports
- Generated artifacts

Future use cases:

- Batch jobs
- RAG document staging
- Fine-grained environment partitioning

### 4. CloudWatch Log Group

- Holds assistant runtime logs once you add hosted components
- Gives a named destination up front so later Lambda, ECS, or batch work lands consistently

### 5. IAM Runtime Role

- Central permission boundary for Bedrock access
- Also grants limited access to the project S3 bucket and log group
- Intended for future AWS-hosted workloads first
- Can be assumed by local developers later if you choose to wire that into your AWS CLI config

## Repository Mapping

- [app](/Users/nathanmalitz/Code/hybrid-ai-platform/app): Python assistant package
- [infra](/Users/nathanmalitz/Code/hybrid-ai-platform/infra): Terraform modules and `dev` environment
- [docs](/Users/nathanmalitz/Code/hybrid-ai-platform/docs): operating notes and architecture records

## Operational Flow

1. Terraform provisions S3, CloudWatch, and IAM.
2. The developer configures `.env` and an AWS profile.
3. The Python CLI loads config from `.env` plus local AWS credentials.
4. The assistant sends prompts to Claude through Bedrock's Converse API.
5. Outputs can later be saved to S3 or emitted to hosted runtimes without changing the core architecture.

## Future Extension Points

- Add a FastAPI service on top of the existing `app/services` layer
- Add S3-backed prompt and result persistence
- Add Bedrock Guardrails and tracing
- Move Terraform state to S3 + DynamoDB for team workflows
- Introduce ECS or Lambda once the assistant needs long-running or shared execution
