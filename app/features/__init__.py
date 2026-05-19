"""
Feature gating system for TK-AI monetization.

This module defines feature availability by user tier and provides
utilities for checking feature access and usage limits.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class UserTier(Enum):
    """User subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass
class FeatureLimits:
    """Usage limits for a feature."""
    monthly_conversations: int = 0
    storage_gb: int = 0
    api_calls_per_hour: int = 0
    max_sessions: int = 0
    advanced_models: bool = False
    cloud_sync: bool = False
    export_formats: list = None
    priority_support: bool = False
    team_collaboration: bool = False
    custom_integrations: bool = False

    def __post_init__(self):
        if self.export_formats is None:
            self.export_formats = ["txt"]


# Feature limits by tier
TIER_LIMITS = {
    UserTier.FREE: FeatureLimits(
        monthly_conversations=50,
        storage_gb=0,  # Local only
        api_calls_per_hour=10,
        max_sessions=10,
        advanced_models=False,
        cloud_sync=False,
        export_formats=["txt"],
    ),
    UserTier.PRO: FeatureLimits(
        monthly_conversations=-1,  # Unlimited
        storage_gb=5,
        api_calls_per_hour=100,
        max_sessions=100,
        advanced_models=True,
        cloud_sync=True,
        export_formats=["txt", "json", "pdf", "docx"],
        priority_support=True,
    ),
    UserTier.ENTERPRISE: FeatureLimits(
        monthly_conversations=-1,  # Unlimited
        storage_gb=-1,  # Unlimited
        api_calls_per_hour=1000,
        max_sessions=-1,  # Unlimited
        advanced_models=True,
        cloud_sync=True,
        export_formats=["txt", "json", "pdf", "docx", "html"],
        priority_support=True,
        team_collaboration=True,
        custom_integrations=True,
    ),
}


class FeatureGate:
    """Manages feature access control."""

    def __init__(self, user_tier: UserTier):
        self.user_tier = user_tier
        self.limits = TIER_LIMITS[user_tier]

    def can_access_feature(self, feature: str) -> bool:
        """Check if user can access a specific feature."""
        feature_map = {
            "unlimited_conversations": self.limits.monthly_conversations == -1,
            "advanced_models": self.limits.advanced_models,
            "cloud_sync": self.limits.cloud_sync,
            "export_pdf": "pdf" in self.limits.export_formats,
            "export_docx": "docx" in self.limits.export_formats,
            "export_html": "html" in self.limits.export_formats,
            "priority_support": self.limits.priority_support,
            "team_collaboration": self.limits.team_collaboration,
            "custom_integrations": self.limits.custom_integrations,
        }
        return feature_map.get(feature, False)

    def get_limit(self, limit_type: str) -> Any:
        """Get a specific limit value."""
        limit_map = {
            "monthly_conversations": self.limits.monthly_conversations,
            "storage_gb": self.limits.storage_gb,
            "api_calls_per_hour": self.limits.api_calls_per_hour,
            "max_sessions": self.limits.max_sessions,
        }
        return limit_map.get(limit_type)

    def is_within_limit(self, current_usage: int, limit_type: str) -> bool:
        """Check if current usage is within allowed limits."""
        limit = self.get_limit(limit_type)
        if limit == -1:  # Unlimited
            return True
        return current_usage < limit


def get_feature_gate(user_tier: str) -> FeatureGate:
    """Factory function to create FeatureGate for user tier."""
    try:
        tier = UserTier(user_tier.lower())
        return FeatureGate(tier)
    except ValueError:
        # Default to free tier for unknown tiers
        return FeatureGate(UserTier.FREE)


# Convenience functions for common checks
def can_use_advanced_models(user_tier: str) -> bool:
    """Check if user can use advanced AI models."""
    return get_feature_gate(user_tier).can_access_feature("advanced_models")

def can_export_format(user_tier: str, format_type: str) -> bool:
    """Check if user can export to specific format."""
    return get_feature_gate(user_tier).can_access_feature(f"export_{format_type}")

def get_conversation_limit(user_tier: str) -> int:
    """Get monthly conversation limit for user."""
    return get_feature_gate(user_tier).get_limit("monthly_conversations")