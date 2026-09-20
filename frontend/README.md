# Solus Frontend (React + AgentCore bridge, Cognito + Amplify)

## Status
UI, chat panel, auth gate, and bridge routes are implemented and the static
paths are verified (`/api/health`, validation errors, build). A live end to
end invoke through the bridge needs valid AWS credentials: the lab session
creds expired before that check could run (same `voc-cancel-cred` deny the
`agentcore` CLI now returns), so re-run one chat after refreshing creds.

## Run
```bash
cd frontend
npm install
npm run build        # emit dist/ for the bridge to serve
npm run api          # API bridge on 127.0.0.1:8787 (needs AWS creds for live invokes)
npm run dev          # Vite dev server on :5173, /api proxied to :8787
```

Open `http://127.0.0.1:5173/` (dev) or `http://127.0.0.1:8787/` (bridge serving
`dist/`). The chat panel answers through `POST /api/solus/invocations`, which
invokes the deployed runtime through the same sanctioned path as
`agentcore invoke`. The browser never holds AWS credentials.

## Auth
- `src/components/AuthGate.tsx` signs in with Cognito (Amplify Auth) and
  attaches the ID token as a Bearer token. Chat works signed out in dev.
- `server/solus-api.py` verifies the token against the pool JWKS (RS256) when
  `COGNITO_USER_POOL_ID` + `COGNITO_CLIENT_ID` are set; otherwise it runs in
  documented loopback dev mode. Pool IDs default to the deploy values in
  `src/lib/agentcore-client/amplifyConfig.ts` and can be overridden with
  `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID`,
  `VITE_COGNITO_IDENTITY_POOL_ID`, `VITE_AWS_REGION`.
- Bridge env: `AWS_REGION` (default us-east-1), `SOLUS_RUNTIME_ARN`,
  `PORT` (default 8787).

## Generative UI wiring (AG-UI events)
- `calculate_loyalty_discount` result → `SolarSavingsChart` (kWp, PHP savings, payback)
- `book_site_survey` → `SurveyDatePicker` human-in-the-loop approval
- Browser Meralco tariff fetch → `TariffCard`

## Theme
Light solar console (OKLCH tokens in `src/index.css`): warm sand paper, amber
primary, sky/leaf accents. Dark chat-free design; mobile single-column under
768px. CopilotKit was removed in favor of a purpose-built `SolusChat` panel
that talks to the runtime bridge.
