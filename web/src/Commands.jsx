import React, { useEffect, useState } from "react";
import { getJSON, fileRef } from "./lib.js";
import { C, mono, Chip, cardBase, cardHover, pageTitle, sectionLabel, EmptyState, useHover } from "./ui.jsx";
import CopyPrompt from "./Copy.jsx";

// Commands = files under connections/*/commands/ and modules/*/commands/,
// registered as MCP prompts. In Claude Code each one is a slash command.

const invocationFor = (name) => `/mcp__gcontext__${name}`;

function CommandCard({ cmd }) {
  const [h, hp] = useHover();
  const inv = invocationFor(cmd.name);
  return (
    <div {...hp} style={{ ...cardBase, ...(h ? cardHover : null), padding: 14, display: "flex", flexDirection: "column", gap: 9 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 30, height: 23, flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center", background: C.codeBg, color: C.onDark, border: `1px solid ${C.faint}`, borderRadius: 5, fontFamily: mono, fontSize: 11, fontWeight: 600 }}>/{cmd.kind}</span>
        <span title={cmd.path} style={{ flex: 1, minWidth: 0, fontFamily: mono, fontSize: 13.5, fontWeight: 600, color: C.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cmd.name}</span>
      </div>
      {cmd.error ? (
        <p style={{ margin: 0, fontSize: 12, color: C.danger }}>Malformed frontmatter: {cmd.error}</p>
      ) : cmd.description ? (
        <p style={{ margin: 0, fontSize: 12, lineHeight: 1.5, color: C.tMuted }}>{cmd.description}</p>
      ) : (
        <p style={{ margin: 0, fontSize: 12, color: C.faint, fontStyle: "italic" }}>No description yet.</p>
      )}
      {(cmd.args || []).length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {cmd.args.map((a) => (
            <Chip key={a.name} tone={a.required ? "stat" : "none"} title={a.description}>{a.name}{a.required ? "*" : ""}</Chip>
          ))}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontFamily: mono, fontSize: 10.5, color: C.t3, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={cmd.path}>{cmd.path}</span>
        <CopyPrompt icon text={fileRef(cmd.path)} title={`Copy a reference to ${cmd.path}`} />
      </div>
      {!cmd.error && (
        <div style={{ marginTop: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <code style={{ flex: 1, minWidth: 0, fontFamily: mono, fontSize: 11, color: C.tMuted, background: C.subtle, border: `1px solid ${C.inputBorder}`, borderRadius: 8, padding: "6px 10px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{inv}</code>
          <CopyPrompt icon text={inv} title={`Copy ${inv}`} toast="Copied, paste it into your agent" />
        </div>
      )}
    </div>
  );
}

export default function Commands() {
  const [cmds, setCmds] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { getJSON("/api/commands").then(setCmds).catch((e) => setErr(e.message)); }, []);

  if (err) return <div style={{ color: C.danger, fontSize: 13.5, padding: 20 }}>Couldn't load: {err}</div>;
  if (!cmds) return <div style={{ padding: "60px 0", textAlign: "center", color: C.t3, fontSize: 14 }}>Loading…</div>;

  return (
    <div>
      <h1 style={{ ...pageTitle, marginBottom: 5 }}>Commands</h1>
      <p style={{ margin: "0 0 20px", color: C.tMuted, fontSize: 13.5, lineHeight: 1.55, maxWidth: 640 }}>
        All MCP prompts: project commands from <span style={{ fontFamily: mono }}>commands/</span> folders and built-in framework prompts, grouped by owner.
      </p>
      {cmds.length === 0 ? (
        <EmptyState>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.ink, marginBottom: 7 }}>No commands yet</div>
          <p style={{ margin: "0 auto", maxWidth: 480, fontSize: 12.5, lineHeight: 1.6, color: C.tMuted }}>
            Drop a <span style={{ fontFamily: mono, color: C.accent }}>.md</span> (prompt) or <span style={{ fontFamily: mono, color: C.accent }}>.py</span> (script) file into <span style={{ fontFamily: mono }}>connections/&lt;name&gt;/commands/</span> or <span style={{ fontFamily: mono }}>modules/&lt;name&gt;/commands/</span> and restart the server.
          </p>
        </EmptyState>
      ) : (
        <>
          <div style={{ ...sectionLabel, marginBottom: 11 }}>Commands ({cmds.length})</div>
          {(() => {
            const groups = {};
            cmds.forEach((c) => { (groups[c.owner] = groups[c.owner] || []).push(c); });
            const owners = Object.keys(groups).sort((a, b) => a === "framework" ? 1 : b === "framework" ? -1 : a.localeCompare(b));
            return owners.map((owner) => (
              <div key={owner} style={{ marginBottom: 22 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <span style={{ fontFamily: mono, fontSize: 12, fontWeight: 600, color: C.ink, textTransform: "uppercase", letterSpacing: "0.04em" }}>{owner}</span>
                  <span style={{ fontSize: 11, color: C.t3 }}>({groups[owner].length})</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 13 }}>
                  {groups[owner].map((c) => <CommandCard key={c.path} cmd={c} />)}
                </div>
              </div>
            ));
          })()}
        </>
      )}
    </div>
  );
}
