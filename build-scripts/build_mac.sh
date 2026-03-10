#!/bin/zsh
set -e

echo "CamComposite macOS build"
echo

read "VERSION?Enter version number (example: 1.0.0): "

if [[ -z "$VERSION" ]]; then
  echo "Version cannot be empty."
  exit 1
fi

APP_NAME="CamComposite"
PKG_ID="com.camcomposite.app"
FINAL_PKG="release/CamComposite-mac-v${VERSION}.pkg"

echo
echo "Cleaning old build files..."
rm -rf build dist
rm -rf packaging/mac/root
rm -rf packaging/mac/expanded
rm -f packaging/mac/CamComposite-component.pkg
rm -f packaging/mac/CamComposite.pkg

echo
echo "Building .app with PyInstaller..."
pyinstaller build-scripts/camcomposite_mac.spec

echo
echo "Preparing pkg root..."
mkdir -p packaging/mac/root/Applications
cp -R dist/CamComposite.app packaging/mac/root/Applications/

echo
echo "Building component package..."
pkgbuild \
  --root packaging/mac/root \
  --scripts packaging/mac/scripts \
  --component-plist packaging/mac/component.plist \
  --identifier "$PKG_ID" \
  --version "$VERSION" \
  --install-location / \
  packaging/mac/CamComposite-component.pkg

echo
echo "Building final installer package..."
productbuild \
  --package packaging/mac/CamComposite-component.pkg \
  packaging/mac/CamComposite.pkg

echo
echo "Preparing release folder..."
mkdir -p release
mv -f packaging/mac/CamComposite.pkg "$FINAL_PKG"

echo
echo "Cleaning temporary packaging files..."
rm -rf build
rm -rf dist
rm -rf packaging/mac/root
rm -rf packaging/mac/expanded
rm -f packaging/mac/CamComposite-component.pkg

find . -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

echo
echo "Build complete:"
echo "$FINAL_PKG"
git add "$FINAL_PKG"