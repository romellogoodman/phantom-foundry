#!/usr/bin/env sh
# Mirror each face's shippable parts from ../faces into public/ so the site can
# render them: fonts to public/fonts/, proofs (PNG sheets, face.json, checks.json)
# under public/proofs/<face>/proofs/. The cut glyphs and traces come along only
# for faces with Arrow research attempts (the site links to them). The index
# the site lists faces from is the foundry's showing sheet (showing/showing.json,
# written by `foundry showing`), copied to public/proofs/index.json.
set -e
cd "$(dirname "$0")/.."
root=..
[ -f "$root/showing/showing.json" ] || (cd "$root" && .venv/bin/foundry showing >/dev/null)
rm -rf public/fonts public/proofs
mkdir -p public/fonts public/proofs
n=0
for face in "$root"/faces/*/; do
  name=$(basename "$face")
  [ -f "$face/proofs/face.json" ] || continue
  mkdir -p "public/proofs/$name/proofs"
  cp "$face"/proofs/*.png "$face"/proofs/*.json "public/proofs/$name/proofs/" 2>/dev/null || true
  cp "$face"dist/*.otf public/fonts/ 2>/dev/null || true
  if ls "$face"/svg/arrow/*.svg >/dev/null 2>&1; then
    cp -R "$face/glyphs" "public/proofs/$name/glyphs"
    cp -R "$face/svg" "public/proofs/$name/svg"
  fi
  n=$((n + 1))
done
cp "$root/showing/showing.json" public/proofs/index.json
echo "synced $n faces, $(ls public/fonts | wc -l | tr -d ' ') fonts, $(du -sh public | cut -f1) in public/"
