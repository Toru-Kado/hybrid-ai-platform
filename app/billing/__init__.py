"""
User management and billing system for TK-AI.

Handles user tiers, usage tracking, and subscription management.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from app.referrals import get_referral_manager, ReferralBonus


@dataclass
class User:
    """User account information."""
    id: str
    email: str
    tier: str = "free"
    stripe_customer_id: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class UsageRecord:
    """Usage tracking record."""
    user_id: str
    month: str  # YYYY-MM format
    conversations: int = 0
    api_calls: int = 0
    storage_bytes: int = 0
    sessions_created: int = 0
    last_updated: datetime = None

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()


class BillingManager:
    """Manages user billing and usage tracking."""

    def __init__(self, db_path: str = "~/.config/hybrid-ai-platform/billing.db"):
        import os
        self.db_path = os.path.expanduser(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self):
        """Initialize database tables."""
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    tier TEXT NOT NULL DEFAULT 'free',
                    stripe_customer_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS usage_records (
                    user_id TEXT NOT NULL,
                    month TEXT NOT NULL,
                    conversations INTEGER DEFAULT 0,
                    api_calls INTEGER DEFAULT 0,
                    storage_bytes INTEGER DEFAULT 0,
                    sessions_created INTEGER DEFAULT 0,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (user_id, month),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            conn.commit()

    def create_or_update_user(self, user_id: str, email: str, tier: str = "free",
                             stripe_customer_id: Optional[str] = None) -> User:
        """Create or update a user."""
        user = User(
            id=user_id,
            email=email,
            tier=tier,
            stripe_customer_id=stripe_customer_id
        )

        with self.get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users
                (id, email, tier, stripe_customer_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user.id,
                user.email,
                user.tier,
                user.stripe_customer_id,
                user.created_at.isoformat(),
                user.updated_at.isoformat()
            ))
            conn.commit()

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM users WHERE id = ?',
                (user_id,)
            ).fetchone()

            if row:
                return User(
                    id=row['id'],
                    email=row['email'],
                    tier=row['tier'],
                    stripe_customer_id=row['stripe_customer_id'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                )
            return None

    def update_user_tier(self, user_id: str, new_tier: str) -> bool:
        """Update user's subscription tier."""
        old_user = self.get_user(user_id)
        old_tier = old_user.tier if old_user else 'free'

        with self.get_connection() as conn:
            result = conn.execute('''
                UPDATE users
                SET tier = ?, updated_at = ?
                WHERE id = ?
            ''', (new_tier, datetime.utcnow().isoformat(), user_id))
            conn.commit()

            if result.rowcount > 0:
                # Handle referral bonuses if tier changed
                if old_tier == 'free' and new_tier != 'free':
                    self._process_referral_conversion(user_id, new_tier)
                return True
            return False

    def _process_referral_conversion(self, user_id: str, new_tier: str):
        """Process referral conversion and apply bonuses."""
        referral_mgr = get_referral_manager()

        # Mark referral as converted
        referral_mgr.convert_referral(user_id, new_tier)

        # Apply bonuses
        bonus = referral_mgr.complete_referral_bonus(user_id)
        if bonus:
            # Apply referrer bonus (could extend subscription or add credits)
            self._apply_referral_bonus(bonus, user_id, is_referee=True)

        # Check for pending bonuses to apply to referrer
        referrer_bonuses = referral_mgr.get_pending_bonuses(user_id)
        for bonus_info in referrer_bonuses:
            # Apply bonus to referrer
            self._apply_referral_bonus_to_referrer(bonus_info)

    def _apply_referral_bonus(self, bonus: ReferralBonus, user_id: str, is_referee: bool = False):
        """Apply referral bonus to user."""
        # For now, we'll track bonus credits in user metadata
        # In a real implementation, this might extend subscription or add credits
        pass  # Implementation depends on specific bonus structure

    def _apply_referral_bonus_to_referrer(self, bonus_info: dict):
        """Apply bonus to referrer when their referral converts."""
        referrer_id = bonus_info['referral_id'].split('_')[0]  # Extract referrer ID
        # Apply bonus to referrer
        pass  # Implementation depends on bonus structure

    def get_or_create_usage_record(self, user_id: str, month: str = None) -> UsageRecord:
        """Get or create usage record for user/month."""
        if month is None:
            month = datetime.utcnow().strftime("%Y-%m")

        with self.get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM usage_records
                WHERE user_id = ? AND month = ?
            ''', (user_id, month)).fetchone()

            if row:
                return UsageRecord(
                    user_id=row['user_id'],
                    month=row['month'],
                    conversations=row['conversations'],
                    api_calls=row['api_calls'],
                    storage_bytes=row['storage_bytes'],
                    sessions_created=row['sessions_created'],
                    last_updated=datetime.fromisoformat(row['last_updated'])
                )
            else:
                # Create new record
                record = UsageRecord(user_id=user_id, month=month)
                conn.execute('''
                    INSERT INTO usage_records
                    (user_id, month, conversations, api_calls, storage_bytes,
                     sessions_created, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.user_id, record.month, record.conversations,
                    record.api_calls, record.storage_bytes, record.sessions_created,
                    record.last_updated.isoformat()
                ))
                conn.commit()
                return record

    def increment_usage(self, user_id: str, usage_type: str, amount: int = 1) -> bool:
        """Increment usage counter for user."""
        month = datetime.utcnow().strftime("%Y-%m")

        with self.get_connection() as conn:
            # Get or create usage record
            record = self.get_or_create_usage_record(user_id, month)

            # Update the specific counter
            if usage_type == "conversations":
                record.conversations += amount
            elif usage_type == "api_calls":
                record.api_calls += amount
            elif usage_type == "storage_bytes":
                record.storage_bytes += amount
            elif usage_type == "sessions_created":
                record.sessions_created += amount
            else:
                return False

            # Save back to database
            conn.execute('''
                UPDATE usage_records
                SET conversations = ?, api_calls = ?, storage_bytes = ?,
                    sessions_created = ?, last_updated = ?
                WHERE user_id = ? AND month = ?
            ''', (
                record.conversations, record.api_calls, record.storage_bytes,
                record.sessions_created, datetime.utcnow().isoformat(),
                user_id, month
            ))
            conn.commit()
            return True

    def get_current_usage(self, user_id: str) -> Dict[str, Any]:
        """Get current month's usage for user."""
        record = self.get_or_create_usage_record(user_id)
        return {
            "conversations": record.conversations,
            "api_calls": record.api_calls,
            "storage_bytes": record.storage_bytes,
            "sessions_created": record.sessions_created,
            "month": record.month
        }

    def check_usage_limit(self, user_id: str, limit_type: str) -> Dict[str, Any]:
        """Check if user is within usage limits."""
        from .features import get_feature_gate

        user = self.get_user(user_id)
        if not user:
            return {"allowed": False, "reason": "User not found"}

        gate = get_feature_gate(user.tier)
        current_usage = self.get_current_usage(user_id)

        usage_value = current_usage.get(limit_type, 0)
        limit = gate.get_limit(limit_type)

        if limit == -1:  # Unlimited
            return {"allowed": True, "current": usage_value, "limit": "unlimited"}

        allowed = usage_value < limit
        return {
            "allowed": allowed,
            "current": usage_value,
            "limit": limit,
            "remaining": max(0, limit - usage_value)
        }


# Global billing manager instance
_billing_manager = None

def get_billing_manager() -> BillingManager:
    """Get global billing manager instance."""
    global _billing_manager
    if _billing_manager is None:
        _billing_manager = BillingManager()
    return _billing_manager