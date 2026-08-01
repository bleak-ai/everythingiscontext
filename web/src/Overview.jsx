import React, { useEffect, useState } from "react";
import { getJSON, copyText, relSeen } from "./lib.js";
import { C, mono, label } from "./ui.jsx";

// Overview = the whole project on one page: sessions, how to connect,
// connections, modules, commands, and the context ledger. Plain lists.

function CopyLink({ text }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={() => { copyText(text); setDone(true); setTimeout(() => setDone(false), 1200); }}
      style={{ all: "unset", cursor: "pointer", fontFamily: mono, fontSize: 11, color: done ? C.ok : C.accent, flexShrink: 0 }}>
      {done ? "copied" : "copy"}
    </button>
  );
}

function Section({ title, children }) {
  return (
    <section style={{ marginBottom: 30 }}>
      <div style={{ ...label, marginBottom: 10 }}>{title}</div>
      {children}
    </section>
  );
}

const row = { display: "flex", alignItems: "baseline", gap: 10, padding: "6px 0", borderTop: `1px solid ${C.borderInner}`, fontSize: 13, flexWrap: "wrap" };
const dim = { fontFamily: mono, fontSize: 11.5, color: C.t3 };

export default function Overview({ project, sessions }) {
  const [conns, setConns] = useState([]);
  const [mods, setMods] = useState([]);
  const [cmds, setCmds] = useState([]);
  const [ledger, setLedger] = useState([]);

  useEffect(() => {
    getJSON("/api/connections").then(setConns).catch(() => {});
    getJSON("/api/modules").then(setMods).catch(() => {});
    getJSON("/api/commands").then(setCmds).catch(() => {});
    getJSON("/api/ledger").then((d) => setLedger(d.ledger)).catch(() => {});
  }, []);

  if (!project) return <p style={{ ...dim }}>loading…</p>;

  const url = `${location.origin}/mcp`;
  const connectCmd = `claude mcp add --transport http ${project.name} ${url}`;
  const archived = Object.entries(project.archived || {}).map(([cat, items]) => `${items.length} ${cat}`).join(", ");

  return (
    <div>
      <p style={{ margin: "0 0 4px", fontSize: 13.5, color: C.tMuted, maxWidth: 620, lineHeight: 1.6 }}>
        {project.description || "No description in gcontext.yaml."}
      </p>
      <p style={{ ...dim, margin: "0 0 30px" }}>{project.project_dir}</p>

      <Section title="sessions">
        {sessions.length === 0 && <p style={{ ...dim, margin: 0 }}>none. Attach a harness with the command below</p>}
        {sessions.map((s, i) => (
          <div key={s.id || i} style={{ ...row, borderTop: i ? row.borderTop : "none" }}>
            <span style={{ fontFamily: mono, fontWeight: 600 }}>{s.client}</span>
            <span style={dim}>{s.version}</span>
            <span style={{ flex: 1 }} />
            <span style={dim}>last activity {relSeen(s.last_seen)}</span>
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 12 }}>
          <code style={{ fontFamily: mono, fontSize: 11.5, color: C.t2, overflowX: "auto", whiteSpace: "nowrap" }}>{connectCmd}</code>
          <CopyLink text={connectCmd} />
        </div>
        <p style={{ ...dim, margin: "6px 0 0" }}>any MCP client: {url}</p>
      </Section>

      <Section title={`connections · ${conns.length}`}>
        {conns.length === 0 && <p style={{ ...dim, margin: 0 }}>none. Add connections/&lt;service&gt;/connection.yaml</p>}
        {conns.map((c, i) => (
          <div key={c.name} style={{ ...row, borderTop: i ? row.borderTop : "none" }}>
            <span style={{ fontFamily: mono, fontWeight: 600 }}>{c.name}</span>
            <span style={{ fontFamily: mono, fontSize: 11.5, color: c.ready ? C.ok : C.danger }}>
              {c.ready ? "ready" : "missing " + c.secrets.filter((s) => !s.filled).map((s) => s.name).join(", ")}
            </span>
            <span style={{ fontSize: 12.5, color: C.tMuted, flex: 1 }}>{c.description}</span>
          </div>
        ))}
      </Section>

      <Section title={`modules · ${mods.length}`}>
        {mods.length === 0 && <p style={{ ...dim, margin: 0 }}>none</p>}
        {mods.map((m, i) => (
          <div key={m.name} style={{ ...row, borderTop: i ? row.borderTop : "none" }}>
            <span style={{ fontFamily: mono, fontWeight: 600 }}>{m.name}</span>
            <span style={dim}>v{m.version}{m.tags?.length ? " · " + m.tags.join(", ") : ""}</span>
            <span style={{ fontSize: 12.5, color: C.tMuted, flex: 1 }}>{m.description}</span>
          </div>
        ))}
      </Section>

      <Section title={`commands · ${cmds.length}`}>
        {cmds.length === 0 && <p style={{ ...dim, margin: 0 }}>none. Drop .md or .py files into a commands/ folder</p>}
        {cmds.map((c, i) => (
          <div key={c.path} style={{ ...row, borderTop: i ? row.borderTop : "none" }}>
            <span style={{ fontFamily: mono, fontWeight: 600 }}>{c.name}</span>
            {c.error
              ? <span style={{ fontSize: 12, color: C.danger }}>malformed: {c.error}</span>
              : <span style={{ fontSize: 12.5, color: C.tMuted, flex: 1 }}>{c.description}</span>}
            {!c.error && <CopyLink text={`/mcp__gcontext__${c.name}`} />}
          </div>
        ))}
      </Section>

      <Section title="context ledger">
        {ledger.map((p, i) => (
          <div key={p.id} style={{ ...row, borderTop: i ? row.borderTop : "none" }}>
            <span style={{ fontFamily: mono, fontSize: 11.5, color: C.t3, width: 22, flexShrink: 0 }}>{p.id}</span>
            <span style={{ fontFamily: mono, fontSize: 12.5, width: 200, flexShrink: 0 }}>{p.label}</span>
            <span style={{ fontFamily: mono, fontSize: 11.5, flexShrink: 0, color: p.status === "loaded" ? C.ok : p.status === "uncontrolled" ? C.amber : C.t3 }}>{p.status}</span>
            <span style={{ fontSize: 12, color: C.tMuted, flex: 1, minWidth: 160 }}>{p.detail}</span>
          </div>
        ))}
      </Section>

      <p style={{ ...dim, margin: 0 }}>
        {project.has_instructions ? `instructions.md · ${project.instructions_lines} lines` : "no instructions.md"}
        {archived ? ` · archive: ${archived}` : ""}
        {` · gcontext ${project.version}`}
      </p>
    </div>
  );
}
