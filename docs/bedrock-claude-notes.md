# Bedrock Claude Notes

## Runtime Choice

This repo keeps Anthropic Claude on Amazon Bedrock as the primary model runtime.

That still fits the platform goals:

- cloud-hosted inference instead of local model execution
- IAM-based access control and AWS-native observability
- a clean path from local workflows to hosted workloads later

## API Choice

The Python app uses the Bedrock Converse API through `boto3`.

Why:

- it maps cleanly to chat-style prompts
- it avoids model-specific HTTP shaping inside the app
- it leaves room for conversation state and guardrail expansion later

## Model Selection Guidance

- use a Claude target that is enabled in the active AWS account and region
- prefer `BEDROCK_INFERENCE_PROFILE_ID` or `BEDROCK_INFERENCE_PROFILE_ARN` for newer Claude models
- use `BEDROCK_MODEL_ID` only when direct invocation is supported in the target account
- keep ARNs out of `BEDROCK_MODEL_ID`

Observed in live testing for this repository on March 31, 2026:

- `BEDROCK_INFERENCE_PROFILE_ARN` worked for the configured Claude Sonnet 4 target
- direct model invocation returned a Bedrock `ValidationException` when that target required an inference profile

## Guardrail Attachment Model

This repo treats Bedrock guardrails as optional and attachable per flow.

- `BEDROCK_GUARDRAIL_MODE=off`
  The app omits `guardrailConfig`.
- `BEDROCK_GUARDRAIL_MODE=user`
  The app guards only the user prompt.
- `BEDROCK_GUARDRAIL_MODE=all`
  The app guards both the user prompt and the system prompt.

## Configuration Variables

- `AWS_REGION`: region for the Bedrock runtime client
- `AWS_PROFILE`: local AWS profile for development
- `BEDROCK_MODEL_ID`: direct model identifier
- `BEDROCK_INFERENCE_PROFILE_ID`: inference profile selector
- `BEDROCK_INFERENCE_PROFILE_ARN`: inference profile ARN override
- `MODEL_MAX_TOKENS`: default token budget
- `MODEL_TEMPERATURE`: default generation temperature
- `ASSISTANT_SYSTEM_PROMPT`: baseline system behavior

## Permission Notes

For the local CLI, the active AWS identity needs:

- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`
- access to the exact model or inference profile being invoked
- `bedrock:ApplyGuardrail` on the selected guardrail ARN when guardrails are enabled

The CDK-created runtime role is intended for future AWS-hosted workloads. It also includes:

- S3 access for AI assets
- CloudWatch Logs write access for assistant logs

The optional operator role mirrors those permissions for a named IAM user and can also receive extra quota and observability read access.

To scope those IAM policies during deploy, set:

- `BEDROCK_FOUNDATION_MODEL_IDS`
- `BEDROCK_INFERENCE_PROFILE_ARNS`
- `BEDROCK_GUARDRAIL_ARNS`
- `RUNTIME_TRUSTED_PRINCIPAL_ARNS`
- `OPERATOR_USER_NAME`

If the allow-lists are left empty, the runtime and operator roles default to Bedrock invoke access on `*`. Tighten those lists once the target models and inference profiles are stable.

## Account Notes

This repo no longer assumes the original Terraform-era AWS account path.

Before testing Bedrock access:

1. authenticate the AWS CLI to the intended Toru Kado account
2. verify the active account with `aws sts get-caller-identity --profile <profile>`
3. confirm the model or inference profile is enabled in that account and region

## Good Next Enhancements

- persist prompts and outputs to S3
- add streaming responses
- add conversation history support
- add explicit guardrail allow-lists once the production targets settle
