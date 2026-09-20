# Phantom Foundry — website

Specimen site for the revived faces. Vite + React + SCSS (from the prototype boilerplate).

- `npm run dev` — local dev server on :8080
- `npm run build` — production build to `dist/`
- `scripts/sync-faces.sh` — copy compiled fonts and proofs from `../faces/*/` into `public/`

Run the sync script after any `foundry matrix` / `foundry proof` so the site shows the latest build.

## Deploy

Live at https://phantom-foundry.romellogoodman.com (Vercel project `phantom-foundry`, root
directory `website/`). A push to `main` that touches `website/` deploys; other pushes are
skipped. So to publish new builds: `foundry showing`, `scripts/sync-faces.sh`, commit, push.
