import React, { useEffect, useRef, useState } from "react";
import { getJSON } from "./lib.js";
import { C, mono, label } from "./ui.jsx";

// Activity = what crossed from gcontext into the agent, newest first.
// A flat feed from /api/events (in-memory ring buffer, empties on restart);
// a `connect` event starts a session, drawn as a separator. Click a row to
// expand the recorded preview inline. Polls every 3s while visible.

const fmtTime = (ts) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function dayLabel(ts) {
  const d = new Date(ts), now = new Date();
  const day = (a) => new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 86400000);
  if (diff === 0) return "today";
  if (diff === 1) return "yesterday";
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function Row({ e, open, onToggle }) {
  const kindColor = e.error ? C.danger : e.kind === "prompt" ? C.ok : C.t3;
  return (
    <div style={{ borderTop: `1px solid ${C.borderInner}` }}>
      <div onClick={onToggle} style={{ display: "flex", alignItems: "baseline", gap: 10, padding: "6px 0", cursor: e.preview ? "pointer" : "default", fontSize: 12.5, flexWrap: "wrap" }}>
        <span style={{ fontFamily: mono, fontSize: 11, color: C.t3, width: 84, flexShrink: 0, whiteSpace: "nowrap" }}>{fmtTime(e.ts)}</span>
        <span style={{ fontFamily: mono, fontSize: 10.5, color: kindColor, width: 44, flexShrink: 0 }}>{e.error ? "error" : e.kind}</span>
        <span style={{ fontFamily: mono, fontWeight: 600, color: e.error ? C.danger : C.ink, flexShrink: 0 }}>{e.name}</span>
        <span style={{ color: C.tMuted, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.detail}</span>
        <span style={{ fontFamily: mono, fontSize: 11, color: C.t3, flexShrink: 0 }}>{e.tokens_out ? `~${e.tokens_out} tk` : ""}</span>
      </div>
      {open && e.preview && (
        <pre className="gc-scroll" style={{ margin: "0 0 10px 70px", padding: "10px 12px", background: C.subtle, border: `1px solid ${C.borderInner}`, borderRadius: 6, fontFamily: mono, fontSize: 11.5, lineHeight: 1.7, whiteSpace: "pre-wrap", overflow: "auto", maxHeight: 300 }}>
          {e.preview}{e.preview.length >= 400 ? "\n┅ first 400 chars, the agent received the rest too" : ""}
        </pre>
      )}
    </div>
  );
}

export default function Activity() {
  const [events, setEvents] = useState(null); // newest first
  const [err, setErr] = useState(null);
  const [open, setOpen] = useState(null);     // event id expanded
  const timer = useRef(null);

  const load = () => getJSON("/api/events?limit=300")
    .then((d) => { setEvents(d.events.slice().reverse()); setErr(null); })
    .catch((e) => setErr(e.message));

  useEffect(() => {
    load();
    timer.current = setInterval(() => { if (!document.hidden) load(); }, 3000);
    const onFocus = () => { if (!document.hidden) load(); };
    window.addEventListener("focus", onFocus);
    return () => { clearInterval(timer.current); window.removeEventListener("focus", onFocus); };
  }, []);

  if (err) return <p style={{ fontFamily: mono, fontSize: 12, color: C.danger }}>{err}</p>;
  if (!events) return <p style={{ fontFamily: mono, fontSize: 11.5, color: C.t3 }}>loading…</p>;
  if (events.length === 0) {
    return <p style={{ fontFamily: mono, fontSize: 11.5, color: C.t3 }}>no activity yet. Events appear here as harnesses connect and call tools. The feed empties on restart.</p>;
  }

  return (
    <div>
      <div style={{ ...label, marginBottom: 10 }}>activity · newest first · empties on restart</div>
      {events.map((e) => (
        <React.Fragment key={e.id}>
          {e.kind === "connect" && (
            <div style={{ fontFamily: mono, fontSize: 10.5, color: C.t3, padding: "14px 0 4px", letterSpacing: ".06em" }}>
              session · {e.name} {e.detail} · {dayLabel(e.ts)} {fmtTime(e.ts)}
            </div>
          )}
          {e.kind !== "connect" && (
            <Row e={e} open={open === e.id} onToggle={() => setOpen(open === e.id ? null : e.id)} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
