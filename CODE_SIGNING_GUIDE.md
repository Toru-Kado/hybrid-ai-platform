# Code Signing & Distribution Setup

This guide explains how to set up code signing and notarization for TK-AI desktop app distribution.

## Prerequisites

### Apple Developer Program (macOS)
1. Join the [Apple Developer Program](https://developer.apple.com/programs/) ($99/year)
2. Create an App Store Connect API key or use your Apple ID
3. Generate certificates in Xcode or via developer.apple.com

### Windows Code Signing Certificate
1. Purchase a code signing certificate from a trusted CA (e.g., DigiCert, GlobalSign)
2. Export as `.p12` file with private key

## Setup Instructions

### 1. macOS Code Signing

#### Option A: Xcode (Recommended)
```bash
# Open Xcode and go to Preferences > Accounts
# Add your Apple ID and select your team
# Download certificates automatically
```

#### Option B: Manual Certificate Installation
1. Download certificates from [developer.apple.com](https://developer.apple.com/account/resources/certificates)
2. Double-click `.cer` files to install in Keychain
3. Find your Developer ID certificate hash:
```bash
security find-identity -v -p codesigning
```

#### Environment Variables for macOS
```bash
export CSC_IDENTITY_AUTO_DISCOVERY=true
# OR
export CSC_NAME="Developer ID Application: Your Name (TEAM_ID)"

# For notarization
export APPLE_ID="your-email@example.com"
export APPLE_ID_PASSWORD="app-specific-password"
export APPLE_TEAM_ID="YOUR_TEAM_ID"
```

### 2. Windows Code Signing

#### Certificate Setup
1. Place your `.p12` certificate file in `certificates/win-certificate.p12`
2. Set environment variable:
```bash
export WINCERT_PASSWORD="your-certificate-password"
```

#### Environment Variables for Windows
```bash
export WIN_CSC_LINK="certificates/win-certificate.p12"
export WIN_CSC_KEY_PASSWORD="your-certificate-password"
```

### 3. Linux Code Signing
Linux builds (AppImage, deb, rpm) don't require code signing for distribution.

## Build Commands

### Signed Builds
```bash
# macOS (with signing & notarization)
CSC_IDENTITY_AUTO_DISCOVERY=true \
APPLE_ID="your-email@example.com" \
APPLE_ID_PASSWORD="app-specific-password" \
APPLE_TEAM_ID="YOUR_TEAM_ID" \
npm run desktop:dist

# Windows (with signing)
WIN_CSC_LINK="certificates/win-certificate.p12" \
WIN_CSC_KEY_PASSWORD="password" \
npm run desktop:dist

# Linux (no signing needed)
npm run desktop:dist
```

### Unsigned Builds (Development)
```bash
npm run desktop:pack  # Creates unsigned app
```

## Distribution Files

After successful build, you'll find these files in `release/`:

### macOS
- `TK-AI-1.1.0.dmg` - Signed DMG installer (124MB)
- `TK-AI-1.1.0-mac.zip` - Signed ZIP archive (119MB)
- `latest-mac.yml` - Auto-updater manifest

### Windows
- `TK-AI-1.1.0.exe` - NSIS installer
- `TK-AI-1.1.0-win.zip` - ZIP archive

### Linux
- `TK-AI-1.1.0.AppImage` - Portable AppImage
- `TK-AI-1.1.0.deb` - Debian package
- `TK-AI-1.1.0.rpm` - RPM package

## Testing Signed Builds

### macOS
```bash
# Verify signature
codesign -dv --verbose=4 "release/mac/TK-AI.app"

# Verify notarization
spctl -a -t exec -vv "release/mac/TK-AI.app"
```

### Windows
```bash
# Verify signature (requires signtool)
signtool verify /pa "release/win/TK-AI-1.1.0.exe"
```

## CI/CD Setup

For automated builds, set these secrets in your GitHub repository:

### GitHub Secrets
```
APPLE_ID: your-email@example.com
APPLE_ID_PASSWORD: app-specific-password
APPLE_TEAM_ID: YOUR_TEAM_ID
WIN_CSC_LINK: base64-encoded-p12-certificate
WIN_CSC_KEY_PASSWORD: certificate-password
CSC_IDENTITY_AUTO_DISCOVERY: true
```

### GitHub Actions Workflow
```yaml
- name: Build and Release
  run: npm run desktop:dist
  env:
    APPLE_ID: ${{ secrets.APPLE_ID }}
    APPLE_ID_PASSWORD: ${{ secrets.APPLE_ID_PASSWORD }}
    APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
    WIN_CSC_LINK: ${{ secrets.WIN_CSC_LINK }}
    WIN_CSC_KEY_PASSWORD: ${{ secrets.WIN_CSC_KEY_PASSWORD }}
    CSC_IDENTITY_AUTO_DISCOVERY: ${{ secrets.CSC_IDENTITY_AUTO_DISCOVERY }}
```

## Troubleshooting

### macOS Issues
- **"Developer ID Application" certificate not found**: Install certificates from developer.apple.com
- **Notarization failed**: Check Apple ID credentials and team ID
- **Gatekeeper blocks app**: App needs to be notarized for macOS 10.15+

### Windows Issues
- **Certificate not recognized**: Ensure certificate is from trusted CA
- **Password incorrect**: Double-check certificate export password

### General Issues
- **Build fails with signing**: Try unsigned build first (`npm run desktop:pack`)
- **Large file sizes**: Enable ASAR compression in electron-builder config
- **Missing icons**: Ensure all icon formats exist in `desktop/assets/`

## Security Notes

- Never commit certificate files to version control
- Use environment variables for passwords, not config files
- Rotate certificates regularly (Apple certs expire annually)
- Store certificates securely (password-protected, encrypted storage)

## Alternative: GitHub Actions

For fully automated cross-platform builds, consider using GitHub Actions with pre-configured workflows for Electron apps.