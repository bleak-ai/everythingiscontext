import React, { useEffect, useState } from "react";
import { getJSON } from "./lib.js";
import { C, mono } from "./ui.jsx";
import Overview from "./Overview.jsx";
import Files from "./Files.jsx";
import Activity from "./Activity.jsx";

// Read-only local dashboard for one gcontext project: a plain sidebar and
// three views. Every view fetches fresh from /api/*; refetch on tab focus.

const SECTIONS = ["overview", "files", "activity"];
const savedSection = () => {
  const s = localStorage.getItem("gc.section");
  return SECTIONS.includes(s) ? s : "overview";
};

function Sidebar({ section, setSection, project, sessions }) {
  return (
    <nav style={{ width: 190, flexShrink: 0, borderRight: `1px solid ${C.border}`, padding: "28px 20px", display: "flex", flexDirection: "column", gap: 4, position: "sticky", top: 0, height: "100vh", boxSizing: "border-box" }}>
      <div style={{ fontFamily: mono, fontSize: 14, fontWeight: 600, marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={project?.project_dir}>
        {project?.name || "gcontext"}
      </div>
      <div style={{ fontFamily: mono, fontSize: 11, color: sessions.length ? C.ok : C.t3, marginBottom: 20 }}>
        {sessions.length ? `● ${sessions.length} connected` : "○ not connected"}
      </div>
      {SECTIONS.map((s) => (
        <button key={s} onClick={() => setSection(s)}
          style={{ all: "unset", cursor: "pointer", fontFamily: mono, fontSize: 12.5, padding: "3px 0", color: section === s ? C.ink : C.t3, fontWeight: section === s ? 600 : 400 }}>
          {section === s ? "› " : "  "}{s}
        </button>
      ))}
      <div style={{ flex: 1 }} />
      {project && <div style={{ fontFamily: mono, fontSize: 10.5, color: C.t3 }}>gcontext {project.version}</div>}
    </nav>
  );
}

export default function App() {
  const [section, setSection] = useState(savedSection);
  const [project, setProject] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [err, setErr] = useState(null);
  useEffect(() => { localStorage.setItem("gc.section", section); }, [section]);

  const refresh = () => {
    getJSON("/api/project").then((p) => { setProject(p); setErr(null); }).catch((e) => setErr(e.message));
    getJSON("/api/sessions").then((d) => setSessions(d.sessions)).catch(() => {});
  };
  useEffect(() => {
    refresh();
    const onFocus = () => { if (!document.hidden) refresh(); };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    return () => { window.removeEventListener("focus", onFocus); document.removeEventListener("visibilitychange", onFocus); };
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.ink, display: "flex" }}>
      <Sidebar section={section} setSection={setSection} project={project} sessions={sessions} />
      <main style={{ flex: 1, minWidth: 0 }}>
        <div style={{ maxWidth: 860, padding: "28px 32px 80px" }}>
          {err && (
            <p style={{ fontFamily: mono, fontSize: 12.5, color: C.danger, marginBottom: 20 }}>
              cannot reach the server: {err}. Is `gcontext up` running?
            </p>
          )}
          {section === "overview" && <Overview project={project} sessions={sessions} />}
          {section === "files" && <Files />}
          {section === "activity" && <Activity />}
        </div>
      </main>
    </div>
  );
}
