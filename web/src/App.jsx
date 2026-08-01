import React, { useEffect, useState } from "react";
import { getJSON, relSeen } from "./lib.js";
import { C, mono, UiProvider, useHover, useIsMobile } from "./ui.jsx";
import Overview from "./Overview.jsx";
import Connections from "./Connections.jsx";
import Modules from "./Modules.jsx";
import Commands from "./Commands.jsx";
import Files from "./Files.jsx";
import Activity from "./Activity.jsx";

// Read-only local dashboard for one gcontext project. The server holds no UI
// state: every section fetches fresh from /api/* and refetches on tab focus.

function NavItem({ active, label, onClick }) {
  const [h, hp] = useHover();
  return (
    <button
      {...hp}
      onClick={onClick}
      style={{ display: "flex", alignItems: "center", width: "100%", height: 36, padding: "0 10px", border: active ? `1px solid ${C.borderStrong}` : "1px solid transparent", borderRadius: 7, fontSize: 13, fontWeight: active ? 600 : 500, cursor: "pointer", marginBottom: 3, textAlign: "left", transition: "background .12s,color .12s,box-shadow .12s", background: active ? "#fff" : h ? C.rowHover : "transparent", color: active ? C.ink : C.t2, boxShadow: active ? "0 1px 2px rgba(28,27,25,.06)" : "none" }}
    >
      {label}
    </button>
  );
}

function Sidebar({ section, setSection, project, sessions }) {
  const lastSeen = (sessions || []).reduce((m, s) => (s.last_seen && s.last_seen > m ? s.last_seen : m), "");
  const connected = (sessions || []).length > 0;
  const nav = [
    { key: "overview", label: "Overview" },
    { key: "connections", label: "Connections" },
    { key: "modules", label: "Modules" },
    { key: "commands", label: "Commands" },
    { key: "files", label: "Files" },
    { key: "activity", label: "Activity" },
  ];
  return (
    <nav className="gc-scroll" style={{ width: 228, height: "100%", flexShrink: 0, background: C.sidebar, borderRight: `1px solid ${C.divider}`, display: "flex", flexDirection: "column", padding: "16px 13px", overflowY: "auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "8px 10px", border: `1px solid ${C.borderStrong}`, borderRadius: 8, background: "#fff", marginBottom: 10, boxShadow: "0 1px 2px rgba(28,27,25,.06)" }}>
        <img src="/icon-light-48x48.png" alt="gcontext" style={{ width: 22, height: 22, display: "block", flexShrink: 0 }} />
        <span title={project?.project_dir} style={{ fontFamily: mono, fontWeight: 600, fontSize: 13, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{project?.name || "gcontext"}</span>
      </div>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 7, alignSelf: "flex-start", fontFamily: mono, fontSize: 10.5, fontWeight: 600, padding: "5px 10px", borderRadius: 20, border: `1px solid ${connected ? C.okBorder : C.inputBorder}`, color: connected ? C.ok : C.t3, background: connected ? C.okBg : "#fff", marginBottom: 8 }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor", display: "inline-block" }} />
        {connected ? `${sessions.length} connected` : lastSeen ? `Last seen ${relSeen(lastSeen)}` : "Not connected"}
      </span>

      {nav.map((it) => (
        <NavItem key={it.key} active={section === it.key} label={it.label} onClick={() => setSection(it.key)} />
      ))}

      <div style={{ flex: 1 }} />
      <div style={{ padding: "10px 11px", border: `1px solid ${C.border}`, borderRadius: 8, background: C.subtle, marginBottom: 10 }}>
        <p style={{ margin: 0, fontSize: 11.5, lineHeight: 1.5, color: C.tMuted }}>
          This dashboard only shows the project. Your <strong style={{ color: C.ink, fontWeight: 600 }}>agent</strong> makes the changes; secret values never appear here.
        </p>
      </div>
      {project && (
        <div style={{ padding: "0 4px", fontFamily: mono, fontSize: 10.5, color: C.t3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={project.project_dir}>
          gcontext {project.version}
        </div>
      )}
    </nav>
  );
}

const SECTIONS = ["overview", "connections", "modules", "commands", "files", "activity"];
const savedSection = () => {
  const s = localStorage.getItem("gc.section");
  return SECTIONS.includes(s) ? s : "overview";
};

export default function App() {
  const [section, setSection] = useState(savedSection);
  const [project, setProject] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [err, setErr] = useState(null);
  const mobile = useIsMobile();
  const [navOpen, setNavOpen] = useState(false);
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

  const go = (key) => { setSection(key); setNavOpen(false); };
  const sidebar = <Sidebar section={section} setSection={go} project={project} sessions={sessions} />;

  return (
    <UiProvider>
      <div style={{ position: "fixed", inset: 0, background: C.bg, display: "flex", flexDirection: mobile ? "column" : "row", overflow: "hidden", color: C.ink }}>
        {mobile ? (
          <>
            <header style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", background: C.sidebar, borderBottom: `1px solid ${C.divider}`, flexShrink: 0 }}>
              <button onClick={() => setNavOpen(true)} aria-label="Open menu" style={{ height: 36, padding: "0 12px", border: `1px solid ${C.border}`, borderRadius: 7, background: "#fff", color: C.ink, fontSize: 16, cursor: "pointer" }}>☰</button>
              <span style={{ fontFamily: mono, fontWeight: 600, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{project?.name || "gcontext"}</span>
            </header>
            {navOpen && (
              <div onClick={() => setNavOpen(false)} style={{ position: "fixed", inset: 0, background: "rgba(28,27,25,.32)", zIndex: 40 }}>
                <div onClick={(e) => e.stopPropagation()} style={{ height: "100%", width: "fit-content" }}>{sidebar}</div>
              </div>
            )}
          </>
        ) : (
          sidebar
        )}
        <main className="gc-scroll" style={{ flex: 1, overflowY: "auto", minWidth: 0 }}>
          <div style={{ maxWidth: 1160, margin: "0 auto", padding: mobile ? "16px 14px 60px" : "22px 30px 60px" }}>
            {err && (
              <div style={{ marginBottom: 22, background: C.missFill, border: `1px solid ${C.missBorder}`, color: C.missText, borderRadius: 7, padding: "11px 13px", fontSize: 13 }}>
                Cannot reach the gcontext server: {err}. Is `gcontext up` running?
              </div>
            )}
            {section === "overview" && <Overview project={project} sessions={sessions} />}
            {section === "connections" && <Connections />}
            {section === "modules" && <Modules />}
            {section === "commands" && <Commands />}
            {section === "files" && <Files />}
            {section === "activity" && <Activity />}
          </div>
        </main>
      </div>
    </UiProvider>
  );
}
