// Calls the Solus AgentCore Runtime through the same-origin API bridge.
// The browser never holds AWS credentials: server/server/solus-api.mjs signs
// SigV4 server-side with ambient credentials. When signed in, the Cognito ID
// token rides along as a Bearer token for the bridge to verify.
export async function invokeSolus(
  prompt: string,
  customerId: string,
  sessionId: string,
  token: string | null,
) {
  const res = await fetch("/api/solus/invocations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ prompt, customer_id: customerId, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Solus invoke failed: ${res.status}`);
  const data = await res.json();
  return String(data.text || "");
}
