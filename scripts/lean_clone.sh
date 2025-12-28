#!/bin/bash
# Sparse + shallow clone to minimize disk usage on Raspberry Pi
# Usage: ./scripts/lean_clone.sh <repo-url> [branch]
# Example: ./scripts/lean_clone.sh https://github.com/MDSonar/RSPI_LocalServer.git main

set -euo pipefail
REPO_URL=${1:-}
BRANCH=${2:-main}

if [[ -z "$REPO_URL" ]]; then
  echo "Usage: $0 <repo-url> [branch]"
  exit 1
fi

TARGET_DIR="RSPI_LocalServer"

if [[ -d "$TARGET_DIR" ]]; then
  echo "Directory $TARGET_DIR already exists. Remove or choose a different location."
  exit 1
fi

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

git init
git remote add origin "$REPO_URL"

git config core.sparseCheckout true
mkdir -p .git/info
cat > .git/info/sparse-checkout << 'EOF'
# Include only essential runtime files
/app/**
/apps/**
/config/**
/requirements.txt
/install.sh
/update.sh
/uninstall.sh
# Exclude Markdown docs and extras
!*.md
!/**/*.md
EOF

git fetch --depth=1 origin "$BRANCH"
git checkout "$BRANCH"

echo "✅ Sparse, shallow clone ready in $(pwd)"
