import { useState } from "react";
import { signIn, signOut, getCurrentUser } from "aws-amplify/auth";

export function useSolusToken() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  return { token, setToken, email, setEmail };
}

export function AuthGate({
  token,
  setToken,
  setEmail,
}: {
  token: string | null;
  setToken: (t: string | null) => void;
  setEmail: (e: string | null) => void;
}) {
  const [addr, setAddr] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      const user = await getCurrentUser();
      setEmail(user.signInDetails?.loginId || user.userId);
    } catch {
      setEmail(null);
    }
  }

  async function doSignIn() {
    setErr("");
    setBusy(true);
    try {
      const { nextStep } = await signIn({ username: addr, password: pw });
      if (nextStep.signInStep === "DONE") {
        const { fetchAuthSession } = await import("aws-amplify/auth");
        const session = await fetchAuthSession();
        const idToken = session.tokens?.idToken?.toString() || null;
        setToken(idToken);
        await refresh();
      } else {
        setErr(`Next step: ${nextStep.signInStep}. Finish it in the Cognito console flow.`);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function doSignOut() {
    await signOut();
    setToken(null);
    setEmail(null);
  }

  if (token) {
    return (
      <div className="solus-chat-user">
        <span>Signed in</span>
        <button onClick={doSignOut}>Sign out</button>
      </div>
    );
  }

  return (
    <form
      className="solus-auth"
      onSubmit={(e) => {
        e.preventDefault();
        doSignIn();
      }}
    >
      <h2>Sign in</h2>
      <p>Cognito signs you in; chat works signed out too (dev loopback).</p>
      <input
        aria-label="Email"
        placeholder="Email"
        autoComplete="email"
        value={addr}
        onChange={(e) => setAddr(e.target.value)}
      />
      <input
        aria-label="Password"
        placeholder="Password"
        type="password"
        autoComplete="current-password"
        value={pw}
        onChange={(e) => setPw(e.target.value)}
      />
      {err && <div className="solus-auth-error">{err}</div>}
      <button className="solus-btn" type="submit" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
