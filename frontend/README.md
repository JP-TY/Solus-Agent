# Solus Frontend (React FAST + CopilotKit, Cognito + Amplify)

## Run
```bash
cd frontend
npm install
npm run dev
```

Configure Amplify hosting with Cognito User Pool; `/api/copilotkit` and
`/api/solus/invocations` are server-side routes that attach the Cognito JWT
and SigV4-sign `InvokeAgentRuntime`. The browser never holds AWS credentials.

## Generative UI wiring (AG-UI events)
- `calculate_loyalty_discount` result → `SolarSavingsChart` (kWp, PHP savings, payback)
- `book_site_survey` → `SurveyDatePicker` human-in-the-loop approval
- Browser Meralco tariff fetch → `TariffCard`
