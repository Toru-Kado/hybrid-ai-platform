# Bedrock Claude Notes

## Runtime Choice

This starter assumes Anthropic Claude on Amazon Bedrock is the primary model runtime.

That choice fits the repository goals:

- Cloud-hosted inference instead of local model execution
- Straightforward IAM-based access control
- A clean path from local development to shared AWS-hosted workloads

## API Choice

The Python app uses the Bedrock Converse API through `boto3`.

Why:

- It maps cleanly to chat-style prompts
- It avoids model-specific HTTP request shaping in the application
- It makes future conversation state handling easier

## Model Selection Guidance

- Use a Claude model that is already enabled in your AWS account and region
- Keep the model ID in `.env` so swapping models does not require code changes
- If your organization standardizes on inference profiles, set `BEDROCK_INFERENCE_PROFILE_ARN` and let the app use that instead of a direct model ID
- Do not put an ARN into `BEDROCK_MODEL_ID`; keep that variable as a plain Bedrock model ID

## Guardrail Attachment Model

This starter treats Bedrock guardrails as optional and attachable per flow.

- `BEDROCK_GUARDRAIL_MODE=off`
  The app omits `guardrailConfig` completely.
- `BEDROCK_GUARDRAIL_MODE=user`
  The app attaches `guardrailConfig` and wraps only the user prompt in `guardContent`.
- `BEDROCK_GUARDRAIL_MODE=all`
  The app attaches `guardrailConfig` and wraps both the user prompt and the system prompt in `guardContent`.

That makes it easy to keep internal orchestration prompts less constrained while applying Bedrock guardrails to user-facing prompts.

## Configuration Variables

- `AWS_REGION`: region for the Bedrock runtime client
- `AWS_PROFILE`: local AWS profile for development
- `BEDROCK_MODEL_ID`: direct model identifier
- `BEDROCK_INFERENCE_PROFILE_ARN`: optional override for inference profile usage
- `BEDROCK_MAX_TOKENS`: default token budget
- `BEDROCK_TEMPERATURE`: default generation temperature
- `ASSISTANT_SYSTEM_PROMPT`: baseline system behavior

## Permission Notes

For the local CLI, your active AWS identity needs:

- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`
- access to the exact resource you invoke, which means:
- the selected foundation model ID if you call Bedrock directly
- the selected inference profile ARN if you use `BEDROCK_INFERENCE_PROFILE_ARN`
- `bedrock:ApplyGuardrail` on the selected guardrail ARN if you use Bedrock guardrails

The Terraform-created IAM role is intended for future AWS-hosted workloads. It also includes:

- S3 access for future prompt and artifact storage
- CloudWatch Logs write access for future hosted execution paths

The local CLI does not automatically assume that role.

If you use an inference profile:

- set `BEDROCK_INFERENCE_PROFILE_ARN` in `.env`
- add that same ARN to `bedrock_allowed_inference_profile_arns` in `infra/environments/dev/terraform.tfvars`
- make sure your local AWS user or profile can invoke that profile as well

If you use a Bedrock guardrail:

- set `BEDROCK_GUARDRAIL_IDENTIFIER` and `BEDROCK_GUARDRAIL_VERSION` in `.env`
- set `BEDROCK_GUARDRAIL_MODE` to `user` or `all`
- add the guardrail ARN to `bedrock_allowed_guardrail_arns` in `infra/environments/dev/terraform.tfvars`
- make sure your local AWS user or profile can call `bedrock:ApplyGuardrail` on that ARN

## Latency and Cost Notes

- Latency will be dominated by the Bedrock round trip, not local CPU
- The Intel Mac is adequate because orchestration cost is low
- Token and model selection choices drive cost much more than local hardware in this design

## Good First Enhancements

- Persist prompts and outputs to S3
- Add streaming responses
- Add conversation history support
- Introduce Bedrock Guardrails when the assistant starts handling sensitive workflows
