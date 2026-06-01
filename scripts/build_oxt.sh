#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OXT_DIR="$PROJECT_ROOT/src/oxt"
BUILD_DIR="$PROJECT_ROOT/build"
OXT_FILE="$BUILD_DIR/Neuro_AI.oxt"

echo "Building LibreOffice Extension (.oxt)..."

mkdir -p "$BUILD_DIR"
cd "$OXT_DIR"

# Zip the contents of src/oxt into the .oxt file
zip -r "$OXT_FILE" . -x "*.pyc" "__pycache__/*" "*.DS_Store"

echo "Build complete: $OXT_FILE"
