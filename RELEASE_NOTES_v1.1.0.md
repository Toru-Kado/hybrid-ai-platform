# TK-AI v1.1.0 Release Notes

**Release Date:** May 11, 2026  
**Download:** [GitHub Releases](https://github.com/Toru-Kado/hybrid-ai-platform/releases/tag/v1.1.0)

## 🎉 What's New

### 🏗️ **Multi-Environment Infrastructure (CDK)**
- **Environment-specific configurations**: Deploy to dev, staging, or production with different settings
- **Smart defaults**: Automatic configuration based on environment type
- **Production-safe**: 90-day log retention, no accidental resource deletion
- **Cross-account support**: Deploy across AWS accounts
- **Bedrock guardrail integration**: Configurable content filtering

### 💰 **Freemium Monetization System**
New modular billing architecture enabling sustainable growth:

#### Pricing Tiers
| Tier | Price | Conversations | Storage | Features |
|------|-------|---------------|---------|----------|
| **Free** | $0 | 50/month | Local | Basic features |
| **Pro** | $10/month | Unlimited | 5GB cloud | Advanced models, export |
| **Enterprise** | $49/month | Unlimited | Unlimited | Teams, custom integrations |

#### Features
- **Feature gating**: Granular control over tier-based access
- **Usage tracking**: Real-time monitoring of conversations, API calls, storage
- **Referral bonuses**: Earn free months by sharing with friends
- **Flexible tiers**: Easy tier management and upgrades

### 📦 **Desktop App Improvements**
- **Code signing infrastructure**: Ready for production distribution
- **Cross-platform packaging**: Configuration for macOS, Windows, Linux
- **Auto-updater support**: Built-in update mechanism
- **Electron 39**: Latest stable version with modern APIs

### 🔒 **Security & Code Quality**
- **All tests passing**: Python, React, CDK test suites validated
- **Code signing guide**: Complete documentation for app distribution
- **Multi-environment safety**: Production safeguards enabled
- **Database versioning**: Schema migrations for future updates

## 📥 **Downloads**

### macOS
- **TK-AI-1.1.0.dmg** - Installer (124 MB)
- **TK-AI-1.1.0-mac.zip** - Portable archive (119 MB)

### Windows & Linux
Build on your platform or use included instructions:
```bash
npm run desktop:dist  # Creates installers for all platforms
```

## 🚀 **Getting Started**

### Installation
1. Download the installer for your platform
2. Install (macOS: drag to Applications, Windows: run installer)
3. Start the app - Python server launches automatically
4. Create your first session

### Upgrading from v1.0.0
- Backup your `.config/hybrid-ai-platform/` directory
- Install v1.1.0
- Your existing sessions will be available (backward compatible)

## 🔄 **Infrastructure Deployment**

Deploy to AWS with multi-environment support:

```bash
# Dev environment
make cdk-deploy-dev

# Staging (validation before production)
make cdk-deploy-staging

# Production
make cdk-deploy-prod
```

See [Multi-Environment Guide](./infra/MULTI_ENV_GUIDE.md) for details.

## 🎯 **API Endpoints (New)**

### Referral Management
- `GET /api/referrals/code` - Get user's referral code
- `GET /api/referrals/stats` - Get referral statistics
- `POST /api/referrals/use` - Apply a referral code

### Feature Gating
Built-in support for tier-based feature access via `X-User-ID` header.

## 📋 **Known Limitations**

- Windows/Linux builds require platform-specific builds (macOS can only build for macOS)
- Code signing certificates needed for production distribution (optional for dev use)
- Bedrock API requires valid AWS credentials
- Local storage default: `~/.config/hybrid-ai-platform/`

## 🔧 **Technical Details**

### Architecture Changes
- Added `app/features/` - Feature gating system
- Added `app/billing/` - User management and billing
- Added `app/referrals/` - Referral code system
- Updated `app/server.py` - New API endpoints
- Updated `infra/stacks/` - Multi-environment support

### Database Schema
New tables for billing and referrals (auto-created on first use):
- `users` - User accounts and tiers
- `usage_records` - Monthly usage tracking
- `referral_codes` - Referral code registry
- `referrals` - Referral relationships

### Dependencies
- **New**: `@electron/notarize` for macOS notarization
- **Verified**: All existing dependencies working with latest versions

## 📖 **Documentation**

- [CLAUDE.md](./CLAUDE.md) - Project overview and architecture
- [CODE_SIGNING_GUIDE.md](./CODE_SIGNING_GUIDE.md) - App distribution guide
- [MONETIZATION.md](./MONETIZATION.md) - Pricing and feature details
- [SALES_PITCH.md](./SALES_PITCH.md) - Marketing materials

## 🐛 **Bug Fixes**

- Fixed import errors in monetization modules
- Fixed dataclass field ordering in referral system
- Fixed contextmanager import in billing module
- Improved error handling in feature gating

## 🙏 **Contributors**

- Infrastructure by Copilot
- Monetization system design and implementation
- Cross-platform testing and validation

## 🔮 **Coming Soon (v1.2.0)**

- Windows and Linux production builds
- Code signing and notarization automation
- AWS production deployment
- Stripe/Paddle payment integration
- Team collaboration features
- Custom model support

---

**Questions?** Open an issue on GitHub  
**Report a bug?** Use the bug report template  
**Have feedback?** We'd love to hear from you!

---

*TK-AI: Private AI. Enterprise Power. Freemium Freedom.*