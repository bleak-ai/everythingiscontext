import React, { useEffect, useState } from "react";
import { getJSON, fileRef, folderRef } from "./lib.js";
import { C, mono, Chip, cardBase, cardHover, cardGrid, pageTitle, sectionLabel, EmptyState, useHover } from "./ui.jsx";
import CopyPrompt from "./Copy.jsx";

// Modules = reusable folders of knowledge (docs, scripts, commands) the agent
// reads on demand. Every file row copies an agent-ready prompt pointing at
// the path inside the gcontext MCP server.

function FileRow({ path }) {
  const [h, hp] = useHover();
  return (
    <div {...hp} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
      <span style={{ fontFamily: mono, fontSize: 11.5, color: h ? C.ink : C.t2, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", transition: "color .12s" }} title={path}>{path}</span>
      <CopyPrompt icon text={fileRef(path)} title={`Copy a reference to ${path}`} />
    </div>
  );
}

function ModuleCard({ mod }) {
  const [h, hp] = useHover();
  const folder = `modules/${mod.name}/`;
  return (
    <div {...hp} style={{ ...cardBase, ...(h ? cardHover : null), padding: 15, display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
        <span style={{ fontFamily: mono, fontSize: 14.5, fontWeight: 600, color: C.ink }}>{mod.name}</span>
        {(mod.tags || []).map((t) => <Chip key={t} tone="stat">{t}</Chip>)}
      </div>
      {mod.description && <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: C.tMuted }}>{mod.description}</p>}
      {mod.files.length > 0 && (
        <div>
          <div style={{ ...sectionLabel, fontSize: 9.5, marginBottom: 5 }}>Files</div>
          {mod.files.map((f) => <FileRow key={f} path={f} />)}
        </div>
      )}
      <div style={{ marginTop: "auto", paddingTop: 4 }}>
        <CopyPrompt text={folderRef(folder)} title={`Copy a reference to ${folder}`} style={{ width: "100%", justifyContent: "center" }} />
      </div>
    </div>
  );
}

export default function Modules() {
  const [mods, setMods] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { getJSON("/api/modules").then(setMods).catch((e) => setErr(e.message)); }, []);

  if (err) return <div style={{ color: C.danger, fontSize: 13.5, padding: 20 }}>Couldn't load: {err}</div>;
  if (!mods) return <div style={{ padding: "60px 0", textAlign: "center", color: C.t3, fontSize: 14 }}>Loading…</div>;

  return (
    <div>
      <h1 style={{ ...pageTitle, marginBottom: 5 }}>Modules</h1>
      <p style={{ margin: "0 0 20px", color: C.tMuted, fontSize: 13.5, lineHeight: 1.55, maxWidth: 640 }}>
        Reusable folders of knowledge and scripts under <span style={{ fontFamily: mono }}>modules/</span>, read by the agent on demand.
      </p>
      {mods.length === 0 ? (
        <EmptyState>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.ink, marginBottom: 7 }}>No modules yet</div>
          <p style={{ margin: "0 auto", maxWidth: 460, fontSize: 12.5, lineHeight: 1.6, color: C.tMuted }}>
            Create a folder under <span style={{ fontFamily: mono, color: C.accent }}>modules/&lt;name&gt;/</span> with the docs or scripts the agent should keep.
          </p>
        </EmptyState>
      ) : (
        <div style={{ ...cardGrid, gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
          {mods.map((m) => <ModuleCard key={m.name} mod={m} />)}
        </div>
      )}
    </div>
  );
}
