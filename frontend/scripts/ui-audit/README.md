# UI audit

A browser audit that proves a visual change did not break the app. For every route, at
desktop (1440x900) and mobile (390x844), and in each theme, it records:

- console errors and uncaught page errors
- horizontal overflow
- WCAG 2.0 A/AA violations (axe-core)
- a *fingerprint* of the page: every heading, button, link (with its href) and input
- a full-page screenshot

`compare.mjs` then diffs two runs: it lists any control that existed before and is gone now.

## Run it

```bash
cd frontend
npm i --no-save playwright @axe-core/playwright     # not a project dependency
npx playwright install chromium

# There is no mock mode: pages render real API data, so audit against a running
# backend. Build the SPA and let FastAPI serve it (same origin as the API):
npm run build
(cd .. && uvicorn app.main:app --port 4174) &

# Protected routes redirect to /login without a session; sign in once and pass
# the token (any account works; register one first if needed):
export AUDIT_TOKEN=$(curl -s -X POST http://localhost:4174/auth/login/json \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"…"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

node scripts/ui-audit/audit.mjs http://localhost:4174 /tmp/ui-after light,dark
# to compare against a run taken before your change:
node scripts/ui-audit/audit.mjs http://localhost:4173 /tmp/ui-before default
node scripts/ui-audit/compare.mjs /tmp/ui-before/report.json /tmp/ui-after/report.json light
```

Themes are chosen by pre-seeding `localStorage['chattam.theme']`; pass `default` to use the
app's own default. A fingerprint difference is only a regression if a control that was
present is missing; renamed `id`s show up as a changed input and need a human look.
