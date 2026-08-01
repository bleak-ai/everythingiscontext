import React, { useEffect, useState } from "react";
import { getJSON, copyText } from "./lib.js";
import { C, mono, Chip, sectionLabel, pageTitle, useUi } from "./ui.jsx";
import CopyPrompt from "./Copy.jsx";

// Overview = what this project is, who is attached, and the context ledger:
// every pipe that inserts context into the agent, in load order.

const STATUS_TONE = { loaded: "ok", "on demand": "none", skipped: "none", uncontrolled: "stat" };

function Sessions({ sessions }) {
  if (!sessions || sessions.length === 0) {
    return <div style={{ fontSize: 12.5, color: C.t3 }}>No harness connected yet. Attach one with the snippets below.</div>;
  }
  return (
    <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, background: "#fff", overflow: "hidden" }}>
      {sessions.map((s, i) => (
        <div key={s.id || i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderTop: i ? `1px solid ${C.borderInner}` : "none", flexWrap: "wrap" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#4a7c59", flexShrink: 0, animation: "gcpulse 2s infinite" }} />
          <span style={{ fontFamily: mono, fontSize: 13, fontWeight: 600, color: C.ink }}>{s.client}</span>
          <span style={{ fontFamily: mono, fontSize: 11, color: C.t3 }}>{s.version}</span>
          <span style={{ flex: 1 }} />
          <span style={{ fontFamily: mono, fontSize: 11, color: C.t3 }}>connected {s.connected} · last activity {s.last_seen}</span>
        </div>
      ))}
    </div>
  );
}

function ConnectSnippets({ name }) {
  const ui = useUi();
  const url = `${location.origin}/mcp`;
  const snippets = [
    { label: "Claude Code", text: `claude mcp add --transport http ${name} ${url}` },
    { label: "Cursor (~/.cursor/mcp.json)", text: JSON.stringify({ mcpServers: { [name]: { url } } }, null, 2) },
    { label: "Codex (~/.codex/config.toml)", text: `[mcp_servers.${name}]\nurl = "${url}"` },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
      {snippets.map((s) => (
        <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 10, border: `1px solid ${C.border}`, borderRadius: 9, background: "#fff", padding: "9px 12px", flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.t2, width: 220, flexShrink: 0 }}>{s.label}</span>
          <code className="gc-scroll" style={{ fontFamily: mono, fontSize: 11.5, color: C.ink, flex: 1, minWidth: 200, overflow: "auto", whiteSpace: "pre" }}>{s.text}</code>
          <CopyPrompt icon text={s.text} title="Copy" toast="Copied, run it in your terminal" />
        </div>
      ))}
    </div>
  );
}

function Ledger() {
  const [ledger, setLedger] = useState([]);
  useEffect(() => { getJSON("/api/ledger").then((d) => setLedger(d.ledger)).catch(() => {}); }, []);
  return (
    <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, background: "#fff", overflow: "hidden" }}>
      {ledger.map((p, i) => (
        <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 11, padding: "9px 14px", borderTop: i ? `1px solid ${C.borderInner}` : "none", flexWrap: "wrap" }}>
          <span style={{ fontFamily: mono, fontSize: 11, fontWeight: 600, color: C.t3, width: 24, flexShrink: 0 }}>{p.id}</span>
          <span style={{ fontFamily: mono, fontSize: 12.5, fontWeight: 600, color: C.ink, width: 210, flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.label}</span>
          <Chip tone={STATUS_TONE[p.status] || "none"}>{p.status}</Chip>
          <span style={{ fontSize: 12, color: C.tMuted, flex: 1, minWidth: 180 }}>{p.detail}</span>
        </div>
      ))}
    </div>
  );
}

export default function Overview({ project, sessions }) {
  if (!project) return <div style={{ padding: "60px 0", textAlign: "center", color: C.t3, fontSize: 14 }}>Loading…</div>;
  const archived = project.archived || {};
  const archivedParts = Object.entries(archived).map(([cat, items]) => `${items.length} ${cat}`);
  return (
    <div>
      <h1 style={{ ...pageTitle, marginBottom: 5 }}>{project.name}</h1>
      <p style={{ margin: "0 0 6px", color: C.tMuted, fontSize: 13.5, lineHeight: 1.55, maxWidth: 640 }}>
        {project.description || "No description in gcontext.yaml yet."}
      </p>
      <div style={{ fontFamily: mono, fontSize: 11.5, color: C.t3, marginBottom: 24 }}>{project.project_dir}</div>

      <div style={{ ...sectionLabel, marginBottom: 9 }}>Connected harnesses</div>
      <Sessions sessions={sessions} />

      <div style={{ ...sectionLabel, margin: "26px 0 9px" }}>Connect a harness</div>
      <ConnectSnippets name={project.name} />

      <div style={{ ...sectionLabel, margin: "26px 0 0" }}>Context ledger</div>
      <p style={{ margin: "6px 0 10px", fontSize: 12.5, color: C.tMuted, maxWidth: 620, lineHeight: 1.55 }}>
        Everything that enters the agent's context from this server, and how.
      </p>
      <Ledger />

      {(project.has_instructions || archivedParts.length > 0) && (
        <div style={{ marginTop: 22, display: "flex", flexDirection: "column", gap: 6, fontSize: 12.5, color: C.tMuted }}>
          {project.has_instructions && (
            <span>System prompt: <span style={{ fontFamily: mono }}>agent.md</span> ({project.instructions_lines} lines)</span>
          )}
          {archivedParts.length > 0 && (
            <span><span style={{ fontFamily: mono }}>archive/</span>: {archivedParts.join(", ")} (not scanned, readable by path)</span>
          )}
        </div>
      )}
    </div>
  );
}
