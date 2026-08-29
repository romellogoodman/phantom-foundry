#!/usr/bin/env sh
# Copy compiled fonts and proofs from ../faces into public/ so the site can render them.
set -e
cd "$(dirname "$0")/.."
for face in ../faces/*/; do
  name=$(basename "$face")
  mkdir -p "public/fonts" "public/proofs/$name"
  cp "$face"dist/*.otf public/fonts/ 2>/dev/null || true
  cp "$face"proofs/*.png "public/proofs/$name/" 2>/dev/null || true
  cp "$face"face.yaml "public/proofs/$name/" 2>/dev/null || true
done
echo "synced: $(ls public/fonts) | $(ls public/proofs)"
