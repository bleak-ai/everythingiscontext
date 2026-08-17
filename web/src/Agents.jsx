import React, { useEffect, useState } from "react";
import { getJSON, fileRef, folderRef } from "./lib.js";
import { C, mono, Chip, cardBase, cardHover, cardGrid, pageTitle, sectionLabel, EmptyState, useHover } from "./ui.jsx";
import CopyPrompt from "./Copy.jsx";

function FileRow({ path }) {
  const [h, hp] = useHover();
  return (
    <div {...hp} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
      <span style={{ fontFamily: mono, fontSize: 11.5, color: h ? C.ink : C.t2, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", transition: "color .12s" }} title={path}>{path}</span>
      <CopyPrompt icon text={fileRef(path)} title={`Copy a reference to ${path}`} />
    </div>
  );
}

function AgentCard({ agent }) {
  const [h, hp] = useHover();
  const folder = `agents/${agent.name}/`;
  return (
    <div {...hp} style={{ ...cardBase, ...(h ? cardHover : null), padding: 15, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
        <span style={{ fontFamily: mono, fontSize: 14.5, fontWeight: 600, color: C.ink }}>{agent.name}</span>
        {(agent.tags || []).map((t) => <Chip key={t} tone="stat">{t}</Chip>)}
      </div>
      {agent.description && <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: C.tMuted }}>{agent.description}</p>}
      {agent.files.length > 0 && (
        <div>
          <div style={{ ...sectionLabel, fontSize: 9.5, marginBottom: 5 }}>Files</div>
          {agent.files.map((f) => <FileRow key={f} path={f} />)}
        </div>
      )}
      <div style={{ marginTop: "auto", paddingTop: 4 }}>
        <CopyPrompt text={folderRef(folder)} title={`Copy a reference to ${folder}`} style={{ width: "100%", justifyContent: "center" }} />
      </div>
    </div>
  );
}

export default function Agents() {
  const [agents, setAgents] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { getJSON("/api/agents").then(setAgents).catch((e) => setErr(e.message)); }, []);

  if (err) return <div style={{ color: C.danger, fontSize: 13.5, padding: 20 }}>Couldn't load: {err}</div>;
  if (!agents) return <div style={{ padding: "60px 0", textAlign: "center", color: C.t3, fontSize: 14 }}>Loading…</div>;

  return (
    <div>
      <h1 style={{ ...pageTitle, marginBottom: 5 }}>Agents</h1>
      <p style={{ margin: "0 0 20px", color: C.tMuted, fontSize: 13.5, lineHeight: 1.55, maxWidth: 640 }}>
        Installed agents from the registry under <span style={{ fontFamily: mono }}>agents/</span>, each with its own steps, commands, and learned data.
      </p>
      {agents.length === 0 ? (
        <EmptyState>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.ink, marginBottom: 7 }}>No agents installed</div>
          <p style={{ margin: "0 auto", maxWidth: 460, fontSize: 12.5, lineHeight: 1.6, color: C.tMuted }}>
            Install one with <span style={{ fontFamily: mono, color: C.accent }}>gcontext add &lt;agent-id&gt;</span> or browse available agents at the registry.
          </p>
        </EmptyState>
      ) : (
        <div style={{ ...cardGrid, gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
          {agents.map((a) => <AgentCard key={a.name} agent={a} />)}
        </div>
      )}
    </div>
  );
}
