#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, TokenRetrievalError

from app.clients import create_runtime_client
from app.config.settings import Settings, SettingsError, load_dotenv
from app.services.chat import ChatService

ROOT_DIR = Path(__file__).resolve().parents[1]
JSII_CACHE_DIR = ROOT_DIR / ".cache" / "jsii"
DEFAULT_PROMPT = "Reply with exactly: bedrock smoke ok"
DEFAULT_EXPECTED_TEXT = "bedrock smoke ok"
DEFAULT_STACK_NAME = "HybridAiPlatformBaseline"
REQUIRED_STACK_OUTPUTS = {
    "AiAssetsBucketName",
    "AssistantLogGroupName",
    "AssistantRuntimeRoleArn",
    "AwsRegion",
    "OrganizationSegment",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run local and AWS smoke checks for the hybrid AI platform."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    local_parser = subparsers.add_parser(
        "local",
        help="Run local static smoke checks.",
    )
    local_parser.set_defaults(func=run_local_smoke)

    bedrock_parser = subparsers.add_parser(
        "bedrock",
        help="Run a live Bedrock invoke smoke check using the app runtime config.",
    )
    bedrock_parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to the dotenv file used for the Bedrock runtime config.",
    )
    bedrock_parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt to send during the live smoke invocation.",
    )
    bedrock_parser.add_argument(
        "--expected-text",
        default=DEFAULT_EXPECTED_TEXT,
        help="Substring expected in the model response.",
    )
    bedrock_parser.set_defaults(func=run_bedrock_smoke)

    stack_parser = subparsers.add_parser(
        "stack",
        help="Verify a deployed baseline stack and its key resources.",
    )
    stack_parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional dotenv file to source AWS_REGION and AWS_PROFILE from.",
    )
    stack_parser.add_argument(
        "--stack-name",
        default=DEFAULT_STACK_NAME,
        help="CloudFormation stack name to verify.",
    )
    stack_parser.add_argument(
        "--aws-region",
        help="AWS region override. Defaults to AWS_REGION from the environment or .env.",
    )
    stack_parser.add_argument(
        "--aws-profile",
        help="AWS profile override. Defaults to AWS_PROFILE from the environment or .env.",
    )
    stack_parser.set_defaults(func=run_stack_smoke)

    deploy_parser = subparsers.add_parser(
        "deploy",
        help="Deploy the baseline stack, then verify the deployed resources.",
    )
    deploy_parser.add_argument(
        "--env-file",
        default=".env",
        help="Optional dotenv file to source AWS_REGION and AWS_PROFILE from.",
    )
    deploy_parser.add_argument(
        "--stack-name",
        default=DEFAULT_STACK_NAME,
        help="CloudFormation stack name to verify after deploy.",
    )
    deploy_parser.add_argument(
        "--aws-region",
        help="AWS region override. Defaults to AWS_REGION from the environment or .env.",
    )
    deploy_parser.add_argument(
        "--aws-profile",
        help="AWS profile override. Defaults to AWS_PROFILE from the environment or .env.",
    )
    deploy_parser.set_defaults(func=run_deploy_smoke)

    return parser.parse_args()


def print_step(message: str) -> None:
    print(f"==> {message}")


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print_step(
        "Running " + " ".join(command) + (f" in {cwd}" if cwd is not None else "")
    )
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        text=True,
        check=True,
    )


def load_env_defaults(env_file: str) -> None:
    load_dotenv(ROOT_DIR / env_file)


def jsii_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("JSII_RUNTIME_PACKAGE_CACHE_ROOT", str(JSII_CACHE_DIR))
    return env


def build_boto3_session(
    *,
    aws_region: str | None,
    aws_profile: str | None,
) -> boto3.session.Session:
    kwargs: dict[str, Any] = {}
    if aws_profile:
        kwargs["profile_name"] = aws_profile
    if aws_region:
        kwargs["region_name"] = aws_region
    return boto3.Session(**kwargs)


def resolve_stack_session(args: argparse.Namespace) -> tuple[boto3.session.Session, str]:
    load_env_defaults(args.env_file)
    aws_region = args.aws_region or os.getenv("AWS_REGION") or "us-east-1"
    aws_profile = args.aws_profile or os.getenv("AWS_PROFILE")
    session = build_boto3_session(aws_region=aws_region, aws_profile=aws_profile)
    return session, aws_region


def format_aws_error(exc: Exception) -> str:
    if isinstance(exc, TokenRetrievalError):
        return (
            "AWS authentication failed because the cached SSO token could not be "
            "refreshed. Run `aws sso login` for the target profile and retry."
        )
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {
            "AccessDenied",
            "AccessDeniedException",
            "ExpiredToken",
            "ExpiredTokenException",
            "InvalidClientTokenId",
            "UnrecognizedClientException",
        }:
            return f"AWS authentication or authorization failed: {exc}"
        return f"AWS API call failed: {exc}"
    return f"AWS authentication failed: {exc}"


def require_cdk() -> None:
    if shutil.which("cdk"):
        return
    raise SystemExit(
        "The AWS CDK CLI is required for local smoke checks. Install `cdk` and retry."
    )


def run_local_smoke(_: argparse.Namespace) -> int:
    require_cdk()
    env = jsii_env()
    run_command(["make", "verify"], cwd=ROOT_DIR, env=env)
    run_command(["make", "infra-test"], cwd=ROOT_DIR, env=env)
    run_command(["cdk", "synth"], cwd=ROOT_DIR / "infra", env=env)
    print_step("Local smoke checks passed")
    return 0


def run_bedrock_smoke(args: argparse.Namespace) -> int:
    try:
        settings = Settings.from_env(ROOT_DIR / args.env_file)
    except SettingsError as exc:
        raise SystemExit(f"Invalid runtime configuration: {exc}") from exc

    if settings.ai_provider != "bedrock":
        raise SystemExit("Bedrock smoke requires AI_PROVIDER=bedrock.")
    if not settings.aws_region:
        raise SystemExit("Bedrock smoke requires AWS_REGION.")

    session = build_boto3_session(
        aws_region=settings.aws_region,
        aws_profile=settings.aws_profile,
    )
    try:
        identity = session.client("sts").get_caller_identity()
    except (BotoCoreError, ClientError) as exc:
        raise SystemExit(format_aws_error(exc)) from exc
    print_step(
        "Resolved AWS identity "
        f"{identity['Arn']} in account {identity['Account']}"
    )

    client = create_runtime_client(settings=settings)
    service = ChatService(client=client, settings=settings)
    result = service.chat(
        prompt=args.prompt,
        max_tokens=32,
        temperature=0,
        guardrail_settings=settings.resolve_guardrail_settings("off"),
    )
    if args.expected_text not in result.response_text:
        raise SystemExit(
            "Bedrock smoke response did not match expectation. "
            f"Expected substring: {args.expected_text!r}. "
            f"Actual response: {result.response_text!r}"
        )

    print(
        json.dumps(
            {
                "response_text": result.response_text,
                "provider": settings.ai_provider,
                "target_id": settings.runtime_target.identifier,
                "request_id": result.request_id,
            },
            indent=2,
        )
    )
    print_step("Bedrock smoke check passed")
    return 0


def _stack_outputs(cloudformation_client: Any, stack_name: str) -> dict[str, str]:
    try:
        response = cloudformation_client.describe_stacks(StackName=stack_name)
    except ClientError as exc:
        raise SystemExit(f"Could not describe stack {stack_name}: {exc}") from exc

    stacks = response.get("Stacks", [])
    if not stacks:
        raise SystemExit(f"Stack {stack_name} was not found.")

    outputs = {
        output["OutputKey"]: output["OutputValue"]
        for output in stacks[0].get("Outputs", [])
        if "OutputKey" in output and "OutputValue" in output
    }
    missing_outputs = sorted(REQUIRED_STACK_OUTPUTS - outputs.keys())
    if missing_outputs:
        raise SystemExit(
            "Stack outputs are incomplete. Missing: " + ", ".join(missing_outputs)
        )
    return outputs


def _role_name_from_arn(role_arn: str) -> str:
    parts = role_arn.split(":", 5)
    if len(parts) != 6:
        raise SystemExit(f"Unsupported IAM role ARN: {role_arn}")
    resource = parts[5]
    prefix = "role/"
    if not resource.startswith(prefix):
        raise SystemExit(f"Unsupported IAM role ARN: {role_arn}")
    return resource[len(prefix) :]


def run_stack_smoke(args: argparse.Namespace) -> int:
    session, aws_region = resolve_stack_session(args)
    try:
        cloudformation_client = session.client("cloudformation", region_name=aws_region)
        outputs = _stack_outputs(cloudformation_client, args.stack_name)

        if outputs["AwsRegion"] != aws_region:
            raise SystemExit(
                f"Stack output AwsRegion={outputs['AwsRegion']} does not match "
                f"the smoke region {aws_region}."
            )

        s3_client = session.client("s3", region_name=aws_region)
        bucket_name = outputs["AiAssetsBucketName"]
        s3_client.head_bucket(Bucket=bucket_name)
        logs_client = session.client("logs", region_name=aws_region)
        log_group_name = outputs["AssistantLogGroupName"]
        log_groups = logs_client.describe_log_groups(
            logGroupNamePrefix=log_group_name
        ).get(
            "logGroups",
            [],
        )
        if not any(group.get("logGroupName") == log_group_name for group in log_groups):
            raise SystemExit(f"Log group {log_group_name} was not found.")

        iam_client = session.client("iam", region_name=aws_region)
        runtime_role_name = _role_name_from_arn(outputs["AssistantRuntimeRoleArn"])
        iam_client.get_role(RoleName=runtime_role_name)

        operator_role_name = outputs.get("DeveloperOperatorRoleName")
        if operator_role_name:
            iam_client.get_role(RoleName=operator_role_name)
    except (BotoCoreError, ClientError) as exc:
        raise SystemExit(format_aws_error(exc)) from exc

    print(
        json.dumps(
            {
                "stack_name": args.stack_name,
                "aws_region": aws_region,
                "outputs": outputs,
            },
            indent=2,
        )
    )
    print_step("Deployed stack smoke check passed")
    return 0


def run_deploy_smoke(args: argparse.Namespace) -> int:
    load_env_defaults(args.env_file)
    env = os.environ.copy()
    if args.aws_region:
        env["AWS_REGION"] = args.aws_region
    if args.aws_profile:
        env["AWS_PROFILE"] = args.aws_profile

    run_command([str(ROOT_DIR / "scripts" / "deploy-baseline.sh")], cwd=ROOT_DIR, env=env)
    return run_stack_smoke(args)


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
