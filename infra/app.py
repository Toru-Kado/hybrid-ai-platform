#!/usr/bin/env python3

import os

from aws_cdk import App, Environment

from stacks.config import PlatformConfig
from stacks.platform_baseline_stack import HybridAiPlatformBaselineStack


app = App()
config = PlatformConfig.from_env()
environment = Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1")),
)

HybridAiPlatformBaselineStack(
    app,
    "HybridAiPlatformBaseline",
    config=config,
    env=environment,
)

app.synth()
