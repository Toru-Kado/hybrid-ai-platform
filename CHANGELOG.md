# Changelog

All notable changes to TK-AI are documented in this file.

## [1.1.0] - 2026-05-11

### Added
- **Monetization System**
  - Feature gating by user tier (Free/Pro/Enterprise)
  - Billing manager with usage tracking
  - Referral code generation and management
  - Referral bonus system with configurable rewards
  - New API endpoints: `/api/referrals/code`, `/api/referrals/stats`, `/api/referrals/use`

- **Multi-Environment Infrastructure**
  - Environment-specific CDK configurations (dev/staging/prod)
  - Smart defaults per environment type
  - Production-safe settings (90-day log retention, no force destroy)
  - Environment-specific Makefile targets
  - Cross-account AWS deployment support

- **Desktop App Enhancements**
  - Code signing infrastructure
  - Cross-platform build configuration (Windows/Linux)
  - Electron 39 support
  - Auto-updater foundation
  - macOS notarization support

- **Documentation**
  - Comprehensive release notes
  - Code signing guide
  - Multi-environment deployment guide
  - Sales pitch and marketing materials
  - Monetization strategy documentation

### Changed
- Updated version to 1.1.0 in all project files
- Improved server module with billing/referral integration
- Enhanced API handler with user context support
- Modular architecture for features and billing

### Fixed
- Import errors in billing module
- Dataclass field ordering in referral system
- Contextmanager import issues
- Server initialization improved

### Dependencies
- Added `@electron/notarize` for macOS app notarization

## [1.0.0] - 2026-04-15

### Initial Release
- Python CLI for Claude via AWS Bedrock
- React 19 + Electron desktop application
- SQLite session persistence
- Real-time streaming responses via SSE
- Message search across sessions
- AWS CDK infrastructure baseline
- Bedrock guardrail support
- Light/dark theme support
- Message export functionality
- Multi-provider support (Bedrock, Anthropic fallback)
- Comprehensive test suites
- Docker-ready architecture

---

## Version Guide

- **v1.1.0** (current): Freemium monetization + multi-environment infrastructure
- **v1.0.0**: Initial feature-complete release

## Roadmap

### v1.2.0 (Q2 2026)
- [ ] Windows and Linux production builds
- [ ] Code signing and notarization automation
- [ ] AWS production deployment
- [ ] Stripe/Paddle payment integration
- [ ] Email verification for sign-ups

### v1.3.0 (Q3 2026)
- [ ] Team collaboration features
- [ ] Custom model support
- [ ] API key management
- [ ] Usage analytics dashboard
- [ ] Mobile app (React Native)

### v1.4.0+ (Future)
- [ ] Self-hosted deployment
- [ ] Custom fine-tuning
- [ ] Plugin system
- [ ] Multi-language support

---

## Release Artifacts

### v1.1.0 Downloads
- **macOS**: TK-AI-1.1.0.dmg (124 MB), TK-AI-1.1.0-mac.zip (119 MB)
- **Windows**: Coming in v1.1.1
- **Linux**: Coming in v1.1.1

### Previous Versions
- **v1.0.0**: macOS only (initial release)