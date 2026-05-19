#!/usr/bin/env python3
"""
CDK app entry point for the hybrid AI platform.

Supports multiple environments (dev, staging, prod) with environment-specific
configurations. Set ENVIRONMENT_TYPE=dev|staging|prod to select the target
environment. Use ENVIRONMENT_NAME to customize the environment label.

Example:
    ENVIRONMENT_TYPE=prod CDK_DEFAULT_REGION=us-east-1 cdk deploy
"""

import os
import sys

from aws_cdk import App, Environment

from stacks.config import EnvironmentType, PlatformConfig, ServerlessConfig
from stacks.platform_baseline_stack import HybridAiPlatformBaselineStack
from stacks.platform_serverless_stack import HybridAiPlatformServerlessStack


def create_app() -> App:
    """Create and configure the CDK app with environment-specific stacks."""
    app = App()

    config = PlatformConfig.from_env()
    serverless_config = ServerlessConfig.from_env()
    environment = Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1")),
    )

    stack_name = "HybridAiPlatformBaseline"
    HybridAiPlatformBaselineStack(
        app,
        stack_name,
        config=config,
        env=environment,
    )

    serverless_stack_name = "HybridAiPlatformServerless"
    HybridAiPlatformServerlessStack(
        app,
        serverless_stack_name,
        config=serverless_config,
        env=environment,
    )

    return app


if __name__ == "__main__":
    try:
        app = create_app()
        app.synth()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
