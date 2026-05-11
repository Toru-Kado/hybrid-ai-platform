"""
Referral bonus system for TK-AI monetization.

Manages referral codes, tracks conversions, and applies bonuses
to both referrers and referees based on subscription tiers.
"""

import sqlite3
import secrets
import string
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class ReferralCode:
    """Referral code information."""
    code: str
    referrer_user_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    max_uses: int = 10
    uses_count: int = 0
    is_active: bool = True


@dataclass
class Referral:
    """Referral relationship record."""
    id: str
    referrer_user_id: str
    referee_user_id: str
    referral_code: str
    status: str  # 'pending', 'converted', 'completed'
    referee_tier: str = 'free'
    bonus_applied: bool = False
    created_at: datetime = None
    converted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class ReferralBonus:
    """Defines bonus structure for different referral scenarios."""

    def __init__(self, referrer_bonus_months: int = 1, referee_bonus_months: int = 1,
                 referrer_credits: int = 0, referee_credits: int = 0):
        self.referrer_bonus_months = referrer_bonus_months
        self.referee_bonus_months = referee_bonus_months
        self.referrer_credits = referrer_credits
        self.referee_credits = referee_credits

    @classmethod
    def for_tier(cls, tier: str) -> 'ReferralBonus':
        """Get bonus structure for a specific tier."""
        bonuses = {
            'free': cls(referrer_bonus_months=1, referee_bonus_months=1),
            'pro': cls(referrer_bonus_months=2, referee_bonus_months=1, referrer_credits=50),
            'enterprise': cls(referrer_bonus_months=3, referee_bonus_months=2, referrer_credits=100, referee_credits=50)
        }
        return bonuses.get(tier.lower(), bonuses['free'])


class ReferralManager:
    """Manages referral codes and bonus distribution."""

    def __init__(self, db_path: str = "~/.config/hybrid-ai-platform/referrals.db"):
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
                CREATE TABLE IF NOT EXISTS referral_codes (
                    code TEXT PRIMARY KEY,
                    referrer_user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    max_uses INTEGER DEFAULT 10,
                    uses_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id TEXT PRIMARY KEY,
                    referrer_user_id TEXT NOT NULL,
                    referee_user_id TEXT NOT NULL,
                    referral_code TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    referee_tier TEXT DEFAULT 'free',
                    bonus_applied BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    converted_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (referral_code) REFERENCES referral_codes (code)
                )
            ''')

            conn.commit()

    def generate_referral_code(self, user_id: str, max_uses: int = 10) -> str:
        """Generate a unique referral code for a user."""
        while True:
            # Generate a 8-character alphanumeric code
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits)
                          for _ in range(8))

            # Check if code already exists
            with self.get_connection() as conn:
                existing = conn.execute(
                    'SELECT code FROM referral_codes WHERE code = ?',
                    (code,)
                ).fetchone()

                if not existing:
                    # Create the referral code
                    conn.execute('''
                        INSERT INTO referral_codes
                        (code, referrer_user_id, created_at, max_uses, uses_count, is_active)
                        VALUES (?, ?, ?, ?, 0, 1)
                    ''', (code, user_id, datetime.utcnow().isoformat(), max_uses))
                    conn.commit()
                    return code

    def get_referral_code(self, user_id: str) -> Optional[ReferralCode]:
        """Get active referral code for a user."""
        with self.get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM referral_codes
                WHERE referrer_user_id = ? AND is_active = 1
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,)).fetchone()

            if row:
                return ReferralCode(
                    code=row['code'],
                    referrer_user_id=row['referrer_user_id'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                    max_uses=row['max_uses'],
                    uses_count=row['uses_count'],
                    is_active=bool(row['is_active'])
                )
            return None

    def use_referral_code(self, code: str, referee_user_id: str) -> bool:
        """Use a referral code for a new user signup."""
        with self.get_connection() as conn:
            # Check if code exists and is valid
            row = conn.execute('''
                SELECT * FROM referral_codes
                WHERE code = ? AND is_active = 1
            ''', (code,)).fetchone()

            if not row:
                return False

            code_data = ReferralCode(
                code=row['code'],
                referrer_user_id=row['referrer_user_id'],
                created_at=datetime.fromisoformat(row['created_at']),
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                max_uses=row['max_uses'],
                uses_count=row['uses_count'],
                is_active=bool(row['is_active'])
            )

            # Check if code has reached max uses
            if code_data.uses_count >= code_data.max_uses:
                return False

            # Check if referee already used a referral
            existing_referral = conn.execute('''
                SELECT id FROM referrals WHERE referee_user_id = ?
            ''', (referee_user_id,)).fetchone()

            if existing_referral:
                return False

            # Create referral record
            referral_id = f"{code_data.referrer_user_id}_{referee_user_id}_{int(datetime.utcnow().timestamp())}"

            conn.execute('''
                INSERT INTO referrals
                (id, referrer_user_id, referee_user_id, referral_code, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            ''', (referral_id, code_data.referrer_user_id, referee_user_id,
                  code, datetime.utcnow().isoformat()))

            # Increment usage count
            conn.execute('''
                UPDATE referral_codes
                SET uses_count = uses_count + 1
                WHERE code = ?
            ''', (code,))

            conn.commit()
            return True

    def convert_referral(self, referee_user_id: str, tier: str = 'free') -> bool:
        """Mark a referral as converted when referee subscribes."""
        with self.get_connection() as conn:
            result = conn.execute('''
                UPDATE referrals
                SET status = 'converted', referee_tier = ?, converted_at = ?
                WHERE referee_user_id = ? AND status = 'pending'
            ''', (tier, datetime.utcnow().isoformat(), referee_user_id))
            conn.commit()
            return result.rowcount > 0

    def complete_referral_bonus(self, referee_user_id: str) -> Optional[ReferralBonus]:
        """Complete referral and apply bonuses. Returns bonus details if applied."""
        with self.get_connection() as conn:
            # Get referral details
            row = conn.execute('''
                SELECT * FROM referrals
                WHERE referee_user_id = ? AND status = 'converted' AND bonus_applied = 0
            ''', (referee_user_id,)).fetchone()

            if not row:
                return None

            referral = Referral(
                id=row['id'],
                referrer_user_id=row['referrer_user_id'],
                referee_user_id=row['referee_user_id'],
                referral_code=row['referral_code'],
                status=row['status'],
                referee_tier=row['referee_tier'],
                bonus_applied=bool(row['bonus_applied']),
                created_at=datetime.fromisoformat(row['created_at']),
                converted_at=datetime.fromisoformat(row['converted_at']) if row['converted_at'] else None,
                completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None
            )

            # Calculate bonus based on referee's tier
            bonus = ReferralBonus.for_tier(referral.referee_tier)

            # Mark bonus as applied
            conn.execute('''
                UPDATE referrals
                SET bonus_applied = 1, completed_at = ?, status = 'completed'
                WHERE id = ?
            ''', (datetime.utcnow().isoformat(), referral.id))
            conn.commit()

            return bonus

    def get_referral_stats(self, user_id: str) -> Dict[str, Any]:
        """Get referral statistics for a user."""
        with self.get_connection() as conn:
            # Count referrals by status
            stats = conn.execute('''
                SELECT
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 'converted' THEN 1 END) as converted,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    COUNT(*) as total
                FROM referrals
                WHERE referrer_user_id = ?
            ''', (user_id,)).fetchone()

            # Get active referral code
            code_row = conn.execute('''
                SELECT code, uses_count, max_uses FROM referral_codes
                WHERE referrer_user_id = ? AND is_active = 1
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,)).fetchone()

            return {
                'total_referrals': stats['total'],
                'pending_referrals': stats['pending'],
                'converted_referrals': stats['converted'],
                'completed_referrals': stats['completed'],
                'active_code': code_row['code'] if code_row else None,
                'code_uses': code_row['uses_count'] if code_row else 0,
                'code_max_uses': code_row['max_uses'] if code_row else 0
            }

    def get_pending_bonuses(self, user_id: str) -> List[Dict[str, Any]]:
        """Get pending referral bonuses for a user."""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT r.*, rc.code as referral_code
                FROM referrals r
                JOIN referral_codes rc ON r.referral_code = rc.code
                WHERE r.referrer_user_id = ? AND r.status = 'converted' AND r.bonus_applied = 0
            ''', (user_id,)).fetchall()

            bonuses = []
            for row in rows:
                bonus = ReferralBonus.for_tier(row['referee_tier'])
                bonuses.append({
                    'referral_id': row['id'],
                    'referee_user_id': row['referee_user_id'],
                    'referee_tier': row['referee_tier'],
                    'bonus_months': bonus.referrer_bonus_months,
                    'bonus_credits': bonus.referrer_credits,
                    'converted_at': row['converted_at']
                })

            return bonuses


# Global referral manager instance
_referral_manager = None

def get_referral_manager() -> ReferralManager:
    """Get global referral manager instance."""
    global _referral_manager
    if _referral_manager is None:
        _referral_manager = ReferralManager()
    return _referral_manager