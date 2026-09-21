import { useEffect, useRef, useState } from "react";

export type ChatMsg = { role: "user" | "agent"; text: string };

const QUICK = [
  "Where is my order ORD-001?",
  "Refund order ORD-002, $139.99, arrived damaged",
  "What are the 550W panel specs?",
  "Size solar for 425 kWh a month",
];

function renderRich(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function ids() {
  let customer = localStorage.getItem("solus-customer") || "";
  let session = localStorage.getItem("solus-session") || "";
  if (!customer) {
    customer = "CUST-" + Math.floor(100 + Math.random() * 900);
    localStorage.setItem("solus-customer", customer);
  }
  if (!session) {
    session = "web-" + Math.random().toString(36).slice(2, 8);
    localStorage.setItem("solus-session", session);
  }
  return { customer, session };
}

async function postChat(prompt: string, token: string | null) {
  const { customer, session } = ids();
  const res = await fetch("/api/solus/invocations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      prompt,
      customer_id: customer,
      session_id: session,
    }),
  });
  if (!res.ok) throw new Error(`Solus answered ${res.status}`);
  const data = await res.json();
  return String(data.text || "Solus had nothing to say.");
}

export function SolusChat({ token }: { token: string | null }) {
  const [msgs, setMsgs] = useState<ChatMsg[]>([
    {
      role: "agent",
      text: "Kumusta! Tell me your DU, monthly bill, roof type, and backup needs. Or try a quick question below.",
    },
  ]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [msgs, busy]);

  async function send(text: string) {
    const prompt = text.trim();
    if (!prompt || busy) return;
    setDraft("");
    setMsgs((m) => [...m, { role: "user", text: prompt }]);
    setBusy(true);
    try {
      const reply = await postChat(prompt, token);
      setMsgs((m) => [...m, { role: "agent", text: reply }]);
    } catch (e) {
      setMsgs((m) => [
        ...m,
        {
          role: "agent",
          text: `Sorry, I could not reach the Solus runtime (${String(e instanceof Error ? e.message : e)}). Is the API bridge running?`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="solus-chat" aria-label="Solus concierge chat">
      <div className="solus-chat-head">
        <h2><span className="sun">☀</span> Solus Concierge</h2>
        <p>Real answers from the live AgentCore runtime.</p>
      </div>
      <div className="solus-chat-log" ref={logRef} data-testid="chat-log">
        {msgs.map((m, i) => (
          <div key={i} className={`solus-msg ${m.role}`}>
            <span className="who">{m.role === "agent" ? "Solus" : "You"}</span>
            {renderRich(m.text)}
          </div>
        ))}
        {busy && (
          <div className="solus-msg agent">
            <span className="who">Solus</span>
            <span className="solus-typing" aria-label="Solus is typing">
              <i /><i /><i />
            </span>
          </div>
        )}
      </div>
      <div className="solus-chips">
        {QUICK.map((q) => (
          <button key={q} className="solus-chip-btn" disabled={busy} onClick={() => send(q)}>
            {q.length > 34 ? q.slice(0, 34) + "…" : q}
          </button>
        ))}
      </div>
      <form
        className="solus-chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
      >
        <textarea
          aria-label="Type a message to Solus"
          placeholder="Type a message…"
          value={draft}
          rows={1}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(draft);
            }
          }}
        />
        <button type="submit" aria-label="Send" disabled={busy}>↑</button>
      </form>
    </aside>
  );
}
