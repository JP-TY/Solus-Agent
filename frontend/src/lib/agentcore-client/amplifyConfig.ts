import { Amplify } from "aws-amplify";

function env(name: string, fallback: string) {
  const v = (import.meta as unknown as {env?: Record<string, string>}).env?.[name];
  return v || fallback;
}

export const COGNITO = {
  userPoolId: env("VITE_COGNITO_USER_POOL_ID", "us-east-1_jec4pw0A0"),
  userPoolClientId: env("VITE_COGNITO_CLIENT_ID", "1ccpiva7igf27jsi391cuni3kf"),
  identityPoolId: env("VITE_COGNITO_IDENTITY_POOL_ID", "us-east-1:9690f47e-9e04-4b25-a924-d2df23d48aa0"),
  region: env("VITE_AWS_REGION", "us-east-1"),
};

export const RUNTIME_ARN =
  "arn:aws:bedrock-agentcore:us-east-1:054833633679:runtime/solus_agent-1T5PxV97sE";

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: COGNITO.userPoolId,
      userPoolClientId: COGNITO.userPoolClientId,
      identityPoolId: COGNITO.identityPoolId,
      loginWith: { email: true },
    },
  },
});
