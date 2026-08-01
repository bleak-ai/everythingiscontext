import React, { useEffect, useState } from "react";
import { getJSON, filePrompt, folderPrompt } from "./lib.js";
import { C, mono, Chip, cardBase, cardHover, cardGrid, pageTitle, sectionLabel, EmptyState, useHover } from "./ui.jsx";
import CopyPrompt from "./Copy.jsx";

// Connections = the services this agent can reach. Secret NAMES with a
// filled/missing state; the values live in secrets.env on this machine.
// Every file row copies an agent-ready prompt pointing at the path inside
// the gcontext MCP server.

function FileRow({ path }) {
  const [h, hp] = useHover();
  return (
    <div {...hp} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
      <span style={{ fontFamily: mono, fontSize: 11.5, color: h ? C.ink : C.t2, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", transition: "color .12s" }} title={path}>{path}</span>
      <CopyPrompt icon text={filePrompt(path)} title={`Copy a prompt to read ${path}`} />
    </div>
  );
}

function ConnectionCard({ conn }) {
  const [h, hp] = useHover();
  const folder = `connections/${conn.name}/`;
  return (
    <div {...hp} style={{ ...cardBase, ...(h ? cardHover : null), padding: 15, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <span style={{ fontFamily: mono, fontSize: 14.5, fontWeight: 600, color: C.ink, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{conn.name}</span>
        <Chip tone={conn.ready ? "ok" : "miss"}>{conn.ready ? "ready" : "missing secrets"}</Chip>
      </div>
      {conn.description && <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: C.tMuted }}>{conn.description}</p>}
      {conn.secrets.length > 0 && (
        <div>
          <div style={{ ...sectionLabel, fontSize: 9.5, marginBottom: 5 }}>Secrets</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {conn.secrets.map((s) => (
              <Chip key={s.name} tone={s.filled ? "ok" : "miss"}>{s.name}</Chip>
            ))}
          </div>
        </div>
      )}
      {conn.deps.length > 0 && (
        <div style={{ fontFamily: mono, fontSize: 11, color: C.t3 }}>deps: {conn.deps.join(", ")}</div>
      )}
      {conn.files.length > 0 && (
        <div>
          <div style={{ ...sectionLabel, fontSize: 9.5, marginBottom: 5 }}>Context files</div>
          {conn.files.map((f) => <FileRow key={f} path={f} />)}
        </div>
      )}
      <div style={{ marginTop: "auto", paddingTop: 4 }}>
        <CopyPrompt text={folderPrompt(folder)} title={`Copy a prompt to explore ${folder}`} style={{ width: "100%", justifyContent: "center" }} />
      </div>
    </div>
  );
}

export default function Connections() {
  const [conns, setConns] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { getJSON("/api/connections").then(setConns).catch((e) => setErr(e.message)); }, []);

  if (err) return <div style={{ color: C.danger, fontSize: 13.5, padding: 20 }}>Couldn't load: {err}</div>;
  if (!conns) return <div style={{ padding: "60px 0", textAlign: "center", color: C.t3, fontSize: 14 }}>Loading…</div>;

  return (
    <div>
      <h1 style={{ ...pageTitle, marginBottom: 5 }}>Connections</h1>
      <p style={{ margin: "0 0 20px", color: C.tMuted, fontSize: 13.5, lineHeight: 1.55, maxWidth: 640 }}>
        Services the agent can reach. Each declares the secret names and Python deps it needs; secret values stay in <span style={{ fontFamily: mono }}>secrets.env</span> on this machine.
      </p>
      {conns.length === 0 ? (
        <EmptyState>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.ink, marginBottom: 7 }}>No connections yet</div>
          <p style={{ margin: "0 auto", maxWidth: 460, fontSize: 12.5, lineHeight: 1.6, color: C.tMuted }}>
            Add one under <span style={{ fontFamily: mono, color: C.accent }}>connections/&lt;service&gt;/connection.yaml</span> with the secret names and deps, plus an <span style={{ fontFamily: mono }}>index.md</span> describing the API in your words.
          </p>
        </EmptyState>
      ) : (
        <div style={{ ...cardGrid, gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
          {conns.map((c) => <ConnectionCard key={c.name} conn={c} />)}
        </div>
      )}
    </div>
  );
}
