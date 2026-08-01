import React, { useEffect, useMemo, useRef, useState } from "react";
import { getJSON, filePrompt } from "./lib.js";
import { C, mono, Chip, GhostBtn, sectionLabel, useHover, useIsMobile, pageTitle, EmptyState } from "./ui.jsx";
import CopyPrompt from "./Copy.jsx";

// Activity = "what crossed from gcontext into my agent, and when". The flat
// /api/events feed (an in-memory ring buffer on the server, newest last) is
// grouped into SESSIONS (a `connect` event opens each one); pick a session on
// the left, skim its crossings, click any to read the recorded preview.
// Polls every 3s while the tab is visible; the buffer empties on restart.

const nfmt = (v) => (v || 0).toLocaleString();
const kfmt = (v) => (v >= 1000 ? (v / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(v));
const fmtTime = (ts) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const fmtHM = (ts) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

function dayLabel(ts) {
  const d = new Date(ts), now = new Date();
  const day = (a) => new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

// The detail's first token, when it reads as a project-relative file path,
// e.g. "connections/x/index.md" or "a.md (12 bytes)" -> "a.md".
function pathRef(detail) {
  const first = (detail || "").split(" ")[0];
  return /^[\w.\-/]+\.\w+$/.test(first) || /^[\w.\-]+\/[\w.\-/]*$/.test(first) ? first : null;
}

// One tier chip per crossing origin: pushed (connect), agent pulled, user pulled.
const TIERS = {
  0: { label: "pushed", color: "#a8492a", bg: "rgba(194,96,58,.10)" },
  1: { label: "agent", color: "#8f7c5f", bg: "rgba(176,154,125,.14)" },
  2: { label: "you", color: "#4a7c59", bg: "rgba(74,124,89,.10)" },
};
const tierOf = (t) => TIERS[t] || TIERS[1];

// Bucket "how much context this call added" so heavy calls are skimmable.
function weight(tokensOut) {
  if (tokensOut >= 5200) return { key: "heavy", color: C.accent, frac: 1, label: "heavy" };
  if (tokensOut >= 2000) return { key: "med", color: "#cf8a63", frac: 0.6, label: "medium" };
  if (tokensOut >= 420) return { key: "light", color: "#c3b7a0", frac: 0.32, label: "light" };
  return { key: "tiny", color: "#d8cfbd", frac: 0.14, label: "minimal" };
}

const label = sectionLabel;
const monoNum = { fontFamily: mono, fontVariantNumeric: "tabular-nums" };

function TierChip({ tier, style }) {
  const t = tierOf(tier);
  return <Chip style={{ color: t.color, background: t.bg, border: "1px solid transparent", minWidth: 46, justifyContent: "center", flexShrink: 0, ...style }}>{t.label}</Chip>;
}

function Bar({ frac, color, w }) {
  return (
    <span style={{ display: "block", width: w, height: 4, borderRadius: 3, background: C.soft, overflow: "hidden" }}>
      <span style={{ display: "block", width: Math.max(frac * w, 3), height: "100%", borderRadius: 3, background: color }} />
    </span>
  );
}

// The one reading surface: light background, ink text, comfortable line height.
function Reader({ children, maxHeight }) {
  return (
    <pre className="gc-scroll" style={{ margin: 0, padding: "16px 18px", background: C.subtle, color: C.ink, border: `1px solid ${C.borderInner}`, fontFamily: mono, fontSize: 12.5, lineHeight: 1.8, borderRadius: 11, whiteSpace: "pre-wrap", overflow: "auto", maxHeight }}>
      {children}
    </pre>
  );
}

// --- session rail item ------------------------------------------------------
function SessionItem({ session, active, selected, onSelect, maxTk }) {
  const [h, hp] = useHover();
  const st = session.startTs;
  return (
    <button {...hp} onClick={onSelect}
      style={{ display: "flex", alignItems: "center", gap: 11, width: "100%", padding: "11px 13px", borderRadius: 10, cursor: "pointer", transition: "all .12s", fontFamily: "inherit",
        border: `1px solid ${selected ? C.borderStrong : (h ? C.borderStrong : C.border)}`, background: "#fff",
        boxShadow: selected ? "0 1px 2px rgba(28,27,25,.06)" : (h ? "0 6px 18px -14px rgba(28,27,25,.4)" : "none") }}>
      <span style={{ width: 9, height: 9, borderRadius: "50%", flexShrink: 0, background: active ? "#4a7c59" : (selected ? C.ink : "#c7c0af"), animation: active ? "gcpulse 2s infinite" : "none" }} />
      <span style={{ display: "flex", flexDirection: "column", gap: 3, minWidth: 0, flex: 1, textAlign: "left" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{active ? "Active session" : `${dayLabel(st)} ${fmtHM(st)}`}</span>
        <span style={{ ...monoNum, fontSize: 11, color: C.t3 }}>{session.events.length} crossing{session.events.length === 1 ? "" : "s"}</span>
      </span>
      <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4, flexShrink: 0 }}>
        <span style={{ ...monoNum, fontSize: 11, fontWeight: 600, color: selected ? C.ink : C.t3 }}>~{kfmt(session.tk)}</span>
        <Bar frac={session.tk / maxTk} color={selected ? C.accent : "#cbb8a4"} w={54} />
      </span>
    </button>
  );
}

// --- one crossing row -------------------------------------------------------
function Row({ e, first, onOpen }) {
  const [h, hp] = useHover();
  const w = weight(e.tokens_out);
  const heavy = e.tokens_out >= 1200;
  const ref = pathRef(e.detail);
  return (
    <div {...hp} onClick={onOpen}
      style={{ display: "flex", gap: 11, padding: "10px 14px", alignItems: "center", cursor: "pointer", transition: "background .12s",
        borderTop: first ? "none" : `1px solid ${C.borderInner}`, background: h ? C.rowHover : e.error ? C.missFill : "transparent" }}>
      <span style={{ ...monoNum, fontSize: 11, color: C.t3, flexShrink: 0, width: 74, whiteSpace: "nowrap", overflow: "hidden" }}>{fmtTime(e.ts)}</span>
      <TierChip tier={e.tier} />
      <span style={{ fontFamily: mono, fontSize: 12, fontWeight: 600, color: e.error ? C.danger : C.ink, flexShrink: 0 }}>{e.name}</span>
      <span style={{ fontSize: 12, color: C.tMuted, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.detail}{e.error ? " · failed" : ""}</span>
      {ref && h && <CopyPrompt icon text={filePrompt(ref)} title={`Copy a prompt to read ${ref}`} style={{ width: 22, height: 22 }} />}
      <span title={`${w.label}: ${nfmt(e.tokens_out)} tokens added to context`} style={{ display: "inline-flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <Bar frac={w.frac} color={w.color} w={44} />
        <span style={{ ...monoNum, fontSize: 11, color: heavy ? C.accent : C.t3, width: 56, textAlign: "right", fontWeight: heavy ? 600 : 400 }}>{nfmt(e.tokens_out)} tk</span>
      </span>
      <span style={{ fontSize: 12, color: "rgba(0,0,0,.3)", flexShrink: 0, width: 12, textAlign: "center" }}>›</span>
    </div>
  );
}

// --- modal: reads a single crossing -----------------------------------------
function Modal({ children, mobile, onClose }) {
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(28,27,25,.34)", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: mobile ? "20px 12px" : "48px 24px", zIndex: 50, overflow: "auto" }}>
      <div onClick={(e) => e.stopPropagation()} className="gc-scroll"
        style={{ width: "min(760px, 100%)", maxHeight: "calc(100vh - 96px)", overflow: "auto", background: "#fff", border: `1px solid ${C.borderStrong}`, borderRadius: 14, boxShadow: "0 30px 70px -24px rgba(28,27,25,.5)", display: "flex", flexDirection: "column", animation: "gcpop .16s ease-out" }}>
        {children}
      </div>
    </div>
  );
}

function EventModal({ e, onClose }) {
  const t = tierOf(e.tier);
  const w = weight(e.tokens_out);
  const hasPreview = !!(e.preview && e.preview.length);
  const ref = pathRef(e.detail);
  const stat = { padding: "12px 15px", borderRight: `1px solid ${C.borderInner}` };
  const statLabel = { ...label, fontSize: 9.5, marginBottom: 4 };
  const statVal = { ...monoNum, fontSize: 14, color: C.ink };
  return (
    <>
      <div style={{ position: "sticky", top: 0, background: "#fff", borderBottom: `1px solid ${C.borderInner}`, padding: "16px 20px", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", zIndex: 1 }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: t.color, flexShrink: 0 }} />
        <span style={{ fontFamily: mono, fontSize: 15.5, fontWeight: 700, color: e.error ? C.danger : C.ink }}>{e.name}</span>
        <TierChip tier={e.tier} />
        {e.error && <Chip tone="miss" style={{ letterSpacing: ".06em" }}>FAILED</Chip>}
        <span style={{ flex: 1 }} />
        <button onClick={onClose} title="Close (Esc)" style={{ width: 30, height: 30, display: "flex", alignItems: "center", justifyContent: "center", border: `1px solid ${C.border}`, borderRadius: 8, background: "#fff", color: C.tMuted, fontSize: 15, cursor: "pointer", flexShrink: 0 }}>✕</button>
      </div>
      <div style={{ padding: 20 }}>
        <div style={{ display: "flex", flexWrap: "wrap", border: `1px solid ${C.borderInner}`, borderRadius: 11, overflow: "hidden", marginBottom: 16 }}>
          <div style={{ ...stat, flex: "1 1 110px" }}>
            <div style={statLabel}>Time</div>
            <div style={statVal}>{new Date(e.ts).toLocaleTimeString()}</div>
          </div>
          <div style={{ ...stat, flex: "1 1 90px" }}>
            <div style={statLabel}>Duration</div>
            <div style={statVal}>{e.duration_ms ? `${nfmt(e.duration_ms)} ms` : "n/a"}</div>
          </div>
          <div style={{ ...stat, flex: "1 1 90px" }}>
            <div style={statLabel}>Tokens in</div>
            <div style={statVal}>{e.tokens_in > 0 ? nfmt(e.tokens_in) + " tk" : "n/a"}</div>
          </div>
          <div style={{ ...stat, flex: "1 1 90px", borderRight: "none" }}>
            <div style={statLabel}>Added to context</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={statVal}>{nfmt(e.tokens_out)} tk</span>
              <Chip style={{ color: w.color, background: w.key === "heavy" ? "rgba(194,96,58,.10)" : "rgba(176,154,125,.14)", border: "1px solid transparent", textTransform: "uppercase", letterSpacing: ".04em" }}>{w.label}</Chip>
            </div>
          </div>
        </div>

        {e.detail && (
          <div style={{ marginBottom: 18 }}>
            <div style={{ ...label, marginBottom: 6 }}>What it was about</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 14px", background: C.subtle, border: `1px solid ${C.borderInner}`, borderRadius: 9 }}>
              <span style={{ fontFamily: mono, fontSize: 13, color: C.ink, lineHeight: 1.6, wordBreak: "break-word", flex: 1 }}>{e.detail}</span>
              {ref && <CopyPrompt icon text={filePrompt(ref)} title={`Copy a prompt to read ${ref}`} />}
            </div>
          </div>
        )}

        <div style={{ ...label, marginBottom: 7 }}>What the agent received</div>
        {hasPreview ? (
          <>
            <Reader maxHeight="46vh">{e.preview}</Reader>
            {e.preview.length >= 400 && <div style={{ marginTop: 9, display: "flex", alignItems: "center", gap: 7, fontSize: 11.5, color: C.t3 }}><span style={{ fontFamily: mono, color: "#8f7c5f" }}>┅</span>First 400 chars shown, the agent received the rest too.</div>}
          </>
        ) : (
          <div style={{ padding: "15px 16px", border: `1px dashed ${e.error ? C.missBorder : C.borderStrong}`, borderRadius: 11, background: e.error ? C.missFill : C.subtle }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 7 }}>
              <span style={{ fontSize: 15 }}>{e.error ? "⚠" : "◌"}</span>
              <span style={{ fontWeight: 600, fontSize: 13.5, color: C.ink }}>{e.error ? "The call failed" : "No preview captured"}</span>
            </div>
            <div style={{ fontSize: 12.5, color: C.tMuted, lineHeight: 1.6 }}>
              {e.error
                ? "This call errored; the message above is what came back."
                : e.kind === "connect"
                ? "A harness connected. Its context comes from the tool descriptions and whatever it pulls next."
                : e.kind === "prompt"
                ? "A command was invoked. The rendered command text went straight into the conversation."
                : "Only the size of this crossing was recorded."}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default function Activity() {
  const mobile = useIsMobile();
  const [flow, setFlow] = useState(null);    // newest-first list; null = loading
  const [err, setErr] = useState(null);
  const [selSession, setSelSession] = useState(0);
  const [modal, setModal] = useState(null);  // {e} | null
  const timer = useRef(null);

  // /api/events returns oldest-first; the grouping below wants newest-first.
  const load = () => getJSON("/api/events?limit=300")
    .then((d) => { setFlow(d.events.slice().reverse()); setErr(null); })
    .catch((e) => setErr(e.message));

  useEffect(() => {
    load();
    timer.current = setInterval(() => { if (!document.hidden) load(); }, 3000);
    const onFocus = () => { if (!document.hidden) load(); };
    window.addEventListener("focus", onFocus);
    return () => { clearInterval(timer.current); window.removeEventListener("focus", onFocus); };
  }, []);

  // Escape closes the modal.
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") setModal(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Split the flat, newest-first feed into sessions (a `connect` event closes one).
  const sessions = useMemo(() => {
    const startTs = (g) => { const c = g.find((e) => e.kind === "connect"); return c ? c.ts : g[g.length - 1].ts; };
    const groups = []; let cur = [];
    for (const e of flow || []) { cur.push(e); if (e.kind === "connect") { groups.push(cur); cur = []; } }
    if (cur.length) groups.push(cur);
    return groups.map((events) => ({ events, startTs: startTs(events), tk: events.reduce((n, e) => n + e.tokens_in + e.tokens_out, 0) }));
  }, [flow]);

  if (err) return <div style={{ color: C.danger, fontSize: 13.5, padding: 20 }}>Couldn't load: {err}</div>;

  const selIdx = Math.min(selSession, Math.max(0, sessions.length - 1));
  const sel = sessions[selIdx];
  const selActive = selIdx === 0;
  const maxTk = Math.max(...sessions.map((s) => s.tk), 1);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 5 }}>
        <h1 style={pageTitle}>Activity</h1>
        <span style={{ flex: 1 }} />
        <GhostBtn onClick={load}>↻ Refresh</GhostBtn>
      </div>
      <p style={{ margin: "0 0 20px", color: C.tMuted, fontSize: 13.5, lineHeight: 1.55, maxWidth: 640 }}>
        Everything that crossed from gcontext into your agent, grouped by session. The feed lives in server memory and empties on restart.
      </p>

      {!flow || flow.length === 0 ? (
        <EmptyState style={{ padding: "48px 28px" }}>
          <div style={{ fontFamily: mono, fontSize: 22, color: C.faint, marginBottom: 12 }}>◌</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.ink, marginBottom: 6 }}>No activity yet</div>
          <div style={{ fontSize: 12.5, color: C.tMuted, lineHeight: 1.6, maxWidth: 360, margin: "0 auto" }}>When a harness connects, a session opens here. Every tool call and command it makes lands under that session, in order.</div>
        </EmptyState>
      ) : (
        <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
          {/* session rail */}
          <div style={{ flex: "0 1 248px", minWidth: 220, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ ...label, padding: "0 2px 2px" }}>Sessions · {sessions.length}</div>
            {sessions.map((s, i) => (
              <SessionItem key={s.startTs + "-" + i} session={s} active={i === 0} selected={i === selIdx} maxTk={maxTk}
                onSelect={() => { setSelSession(i); setModal(null); }} />
            ))}
          </div>

          {/* session detail */}
          <div style={{ flex: "1 1 460px", minWidth: 340 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap", marginBottom: 3 }}>
              <span style={{ fontSize: 19, fontWeight: 600, letterSpacing: "-.01em", color: C.ink }}>{selActive ? "Active session" : `${dayLabel(sel.startTs)} · ${fmtHM(sel.startTs)}`}</span>
              {selActive && <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: mono, fontSize: 10.5, fontWeight: 600, color: "#4a7c59" }}><span style={{ width: 7, height: 7, borderRadius: "50%", background: "#4a7c59", animation: "gcpulse 2s infinite" }} />live</span>}
            </div>
            <div style={{ ...monoNum, fontSize: 12, color: C.t3, marginBottom: 16 }}>
              {selActive ? "Started" : dayLabel(sel.startTs) + " ·"} {fmtTime(sel.startTs)} · {sel.events.length} crossing{sel.events.length === 1 ? "" : "s"} · ~{nfmt(sel.tk)} tokens into context
            </div>

            {/* legend */}
            <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", margin: "0 2px 9px" }}>
              <span style={label}>Crossings</span>
              <span style={{ flex: 1 }} />
              {[0, 1, 2].map((tier) => (
                <span key={tier} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: C.tMuted }}>
                  <span style={{ width: 7, height: 7, borderRadius: 2, background: tierOf(tier).color }} />
                  {tier === 0 ? "pushed" : tier === 1 ? "agent pulled" : "you pulled"}
                </span>
              ))}
            </div>

            {/* feed */}
            <div style={{ borderRadius: 11, border: `1px solid ${C.border}`, background: "#fff", overflow: "hidden" }}>
              {sel.events.map((e, i) => (
                <Row key={`${e.id}-${i}`} e={e} first={i === 0} onOpen={() => setModal({ e })} />
              ))}
            </div>
          </div>
        </div>
      )}

      {modal && (
        <Modal mobile={mobile} onClose={() => setModal(null)}>
          <EventModal e={modal.e} onClose={() => setModal(null)} />
        </Modal>
      )}
    </div>
  );
}
