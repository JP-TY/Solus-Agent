// Calls Solus AgentCore Runtime through the Cognito-authenticated proxy.
// Browser never holds AWS creds; Amplify + Lambda proxy sign SigV4 server-side.
export async function invokeSolus(prompt: string, customerId: string, sessionId: string) {
  const res = await fetch("/api/solus/invocations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, customer_id: customerId, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Solus invoke failed: ${res.status}`);
  return res.json();
}
