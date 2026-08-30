#!/usr/bin/env sh
# Mirror each face's shippable parts from ../faces into public/ so the site can
# render them: fonts to public/fonts/, and dist/ proofs/ glyphs/ svg/ under
# public/proofs/<face>/ with the same relative paths face.json uses. Scans
# (specimens/) stay out — they're fetched, not shipped. Writes public/proofs/index.json.
set -e
cd "$(dirname "$0")/.."
mkdir -p public/fonts public/proofs
faces=""
for face in ../faces/*/; do
  name=$(basename "$face")
  [ -f "$face/proofs/face.json" ] || continue
  rm -rf "public/proofs/$name"
  mkdir -p "public/proofs/$name"
  for d in dist proofs glyphs svg; do
    [ -d "$face/$d" ] && cp -R "$face/$d" "public/proofs/$name/$d"
  done
  cp "$face"dist/*.otf public/fonts/ 2>/dev/null || true
  faces="$faces${faces:+, }\"$name\""
done
printf '{ "faces": [%s] }\n' "$faces" > public/proofs/index.json
echo "synced: $(ls public/fonts | tr '\n' ' ')| $(cat public/proofs/index.json)"
