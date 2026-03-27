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

## Configuration Variables

- `AWS_REGION`: region for the Bedrock runtime client
- `AWS_PROFILE`: local AWS profile for development
- `BEDROCK_MODEL_ID`: direct model identifier
- `BEDROCK_INFERENCE_PROFILE_ARN`: optional override for inference profile usage
- `BEDROCK_MAX_TOKENS`: default token budget
- `BEDROCK_TEMPERATURE`: default generation temperature
- `ASSISTANT_SYSTEM_PROMPT`: baseline system behavior

## Permission Notes

For a useful starter role, the runtime needs:

- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`
- `bedrock:Converse`
- `bedrock:ConverseStream`

This repository also adds:

- S3 access for future prompt and artifact storage
- CloudWatch Logs write access for future hosted execution paths

## Latency and Cost Notes

- Latency will be dominated by the Bedrock round trip, not local CPU
- The Intel Mac is adequate because orchestration cost is low
- Token and model selection choices drive cost much more than local hardware in this design

## Good First Enhancements

- Persist prompts and outputs to S3
- Add retry logic and error classification for throttling or transient failures
- Add conversation history support
- Introduce Bedrock Guardrails when the assistant starts handling sensitive workflows
