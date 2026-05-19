"""Shared CDK utilities for stack and construct modules.

Provides name sanitization, CloudWatch retention mapping, and other
helpers used across both the baseline and serverless stacks.
"""
from __future__ import annotations

import re

from aws_cdk import aws_logs as logs


def sanitize_name(value: str) -> str:
    """Sanitize a name for use in AWS resource identifiers.

    Converts to lowercase, replaces non-alphanumeric characters with hyphens,
    and strips leading/trailing hyphens. Returns a fallback if result is empty.
    """
    sanitized = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return sanitized or "hybrid-ai-platform"


def truncate_name(value: str, limit: int) -> str:
    """Truncate a name to a maximum length, stripping trailing hyphens."""
    return value[:limit].rstrip("-")


def retention_days_from_int(value: int) -> logs.RetentionDays:
    """Map an integer retention value to the CloudWatch RetentionDays enum.

    Raises:
        ValueError: If the value is not a supported CloudWatch retention period.
    """
    retention_map = {
        1: logs.RetentionDays.ONE_DAY,
        3: logs.RetentionDays.THREE_DAYS,
        5: logs.RetentionDays.FIVE_DAYS,
        7: logs.RetentionDays.ONE_WEEK,
        14: logs.RetentionDays.TWO_WEEKS,
        30: logs.RetentionDays.ONE_MONTH,
        60: logs.RetentionDays.TWO_MONTHS,
        90: logs.RetentionDays.THREE_MONTHS,
        120: logs.RetentionDays.FOUR_MONTHS,
        150: logs.RetentionDays.FIVE_MONTHS,
        180: logs.RetentionDays.SIX_MONTHS,
        365: logs.RetentionDays.ONE_YEAR,
        400: logs.RetentionDays.THIRTEEN_MONTHS,
        545: logs.RetentionDays.EIGHTEEN_MONTHS,
        731: logs.RetentionDays.TWO_YEARS,
        1827: logs.RetentionDays.FIVE_YEARS,
        3653: logs.RetentionDays.TEN_YEARS,
        0: logs.RetentionDays.INFINITE,
    }
    try:
        return retention_map[value]
    except KeyError as exc:
        valid = sorted(retention_map.keys())
        raise ValueError(
            f"log_retention_days must be one of {valid} "
            f"(CloudWatch-supported values), got {value}."
        ) from exc
