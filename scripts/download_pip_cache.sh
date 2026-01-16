#!/bin/bash
# Download all pip dependencies for offline installation in Docker

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CACHE_DIR="./backend/.pip-cache"
BACKEND_DIR="./backend"

echo "Creating pip cache directory..."
mkdir -p "$CACHE_DIR"

source "${PROJECT_ROOT}"/scripts/activate_python.sh
echo "Downloading dependencies from pyproject.toml..."
pip download \
  --dest "$CACHE_DIR" \
  --no-binary :all: --only-binary torch,torchvision \
  --extra-index-url https://download.pytorch.org/whl \
  "$BACKEND_DIR"

echo "Downloading SAM3 and its dependencies..."
pip download \
  --dest "$CACHE_DIR" \
  git+https://github.com/facebookresearch/sam3.git

echo "Cache directory: $CACHE_DIR"
echo "Total files: $(ls "$CACHE_DIR" | wc -l)"
echo "Total size: $(du -sh "$CACHE_DIR" | cut -f1)"
echo ""
echo "Cache ready for Docker build. The Dockerfile will use --find-links to install from cache."
