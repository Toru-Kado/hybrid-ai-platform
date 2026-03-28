from __future__ import annotations

import argparse
import json
import logging
import sys

from app.clients.bedrock import BedrockClientError, BedrockRuntimeClient
from app.config.logging import configure_logging
from app.config.settings import Settings, SettingsError
from app.services.chat import ChatService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CLI assistant for invoking Anthropic Claude through Amazon Bedrock."
    )
    parser.add_argument(
        "--prompt",
        help="User prompt. If omitted, the CLI reads from standard input.",
    )
    parser.add_argument(
        "--system",
        help="Optional system prompt. Defaults to ASSISTANT_SYSTEM_PROMPT from the environment.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        help="Override the maximum number of tokens returned by the model.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="Override the Bedrock temperature for this request.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full response payload instead of only the assistant text.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to a dotenv-style file. Defaults to .env in the repository root.",
    )
    parser.add_argument(
        "--guardrails",
        choices=["off", "user", "all"],
        help=(
            "Override Bedrock guardrail handling for this run. "
            "off omits guardrails, user guards only the user prompt, all guards user and system prompts."
        ),
    )
    return parser.parse_args()


def resolve_prompt(args: argparse.Namespace) -> str:
    if args.prompt:
        prompt = args.prompt.strip()
        if prompt:
            return prompt

    if not sys.stdin.isatty():
        piped_prompt = sys.stdin.read().strip()
        if piped_prompt:
            return piped_prompt

    raise SystemExit("Provide --prompt or pipe prompt text on stdin.")


def validate_args(args: argparse.Namespace) -> None:
    if args.max_tokens is not None and args.max_tokens <= 0:
        raise SystemExit("--max-tokens must be greater than zero.")

    if args.temperature is not None and not 0 <= args.temperature <= 1:
        raise SystemExit("--temperature must be between 0 and 1.")


def main() -> int:
    args = parse_args()
    validate_args(args)

    try:
        settings = Settings.from_env(args.env_file)
        guardrail_settings = settings.resolve_guardrail_settings(args.guardrails)
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    configure_logging(
        level=settings.log_level,
        service_name=settings.app_name,
        environment=settings.app_env,
    )

    logger = logging.getLogger(__name__)

    try:
        prompt = resolve_prompt(args)
        client = BedrockRuntimeClient(settings=settings)
        service = ChatService(client=client, settings=settings)
        result = service.chat(
            prompt=prompt,
            system_prompt=args.system,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            guardrail_settings=guardrail_settings,
        )
    except BedrockClientError as exc:
        logger.error(
            "Bedrock invocation failed",
            extra={
                "aws_region": settings.aws_region,
                "target_id": settings.runtime_target.identifier,
                "target_kind": settings.runtime_target.kind,
                "target_source": settings.runtime_target.source_env,
                "error_code": exc.error_code,
                "details": str(exc),
            },
        )
        print(f"Bedrock error: {exc}", file=sys.stderr)
        return 1
    except Exception:
        logger.exception("Unexpected assistant failure")
        print("Unexpected application error. Check logs for details.", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.response_text)

    return 0
