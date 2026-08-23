import React, { useEffect, useMemo, useRef, useState } from "react";
import { getJSON, postJSON, commandInvocation, fileRef, commandPrefix, copyText, getServerName } from "./lib.js";
import { C, mono, EmptyState, useHover, GhostBtn, Field, useIsMobile } from "./ui.jsx";

// Design-handoff surfaces with no equivalent in the shared palette (the dark
// pending bar, the reloaded toast, the dark filter chip). Everything else maps
// onto the C tokens so this tab stays in the dashboard's palette.
const D = {
  barBg: "#26221b", barText: "#f5f1e8", barMuted: "#b5ad9d", barDivider: "#3f392c",
  barGhostBorder: "#4a4335", barGhostText: "#cfc7b6", barGhostHover: "#332d22",
  barBtnBg: "#e8dfc9", barBtnText: "#26221b",
  amberDot: "#e8b45a",
  chipCodeBg: "#3a3428", chipCodeText: "#e8dfc9",
  toastBg: "#1e4a2e", toastText: "#edf5ec", toastMuted: "#bcd4be",
  toastChipBg: "#2a5c3b", toastChipText: "#e2f0e2", toastX: "#9dbca1",
  darkChip: "#3a3226", darkChipText: "#fbf8f1", darkChipCount: "#b5ad9d",
  segBg: "#e3ded2",
};

const SANS = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif";

// --- Icons (24 viewBox, stroke currentColor, rendered at 14px) ---------------

function MagnifierIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0 }}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

function CopyIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function PencilIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d="M17 3a2.83 2.83 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
    </svg>
  );
}

// --- Small controls ----------------------------------------------------------

function Caret({ open, size = 11, color = C.tLabel }) {
  return (
    <span style={{ display: "inline-block", width: 10, fontSize: size, lineHeight: 1, color, flexShrink: 0, textAlign: "center" }}>
      {open ? "▾" : "▸"}
    </span>
  );
}

function Switch({ on, disabled, onClick, title }) {
  return (
    <button onClick={onClick} disabled={disabled} title={title} aria-pressed={on}
      style={{
        all: "unset", boxSizing: "border-box", cursor: disabled ? "default" : "pointer",
        width: 36, height: 21, borderRadius: 999,
        background: on ? C.ok : C.disabled,
        position: "relative", transition: "background .15s", flexShrink: 0,
        opacity: disabled ? 0.45 : 1,
      }}>
      <span style={{
        position: "absolute", top: 3, left: on ? 18 : 3,
        width: 15, height: 15, borderRadius: "50%", background: "#fff",
        boxShadow: "0 1px 3px rgba(28,27,25,.3)",
        transition: "left .15s",
      }} />
    </button>
  );
}

function IconBtn({ title, onClick, children }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick} title={title}
      style={{
        all: "unset", boxSizing: "border-box", cursor: "pointer",
        width: 26, height: 26, borderRadius: 6,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        color: h ? C.ink : C.t3, background: h ? C.soft : "transparent",
        transition: "all .12s", flexShrink: 0,
      }}>
      {children}
    </button>
  );
}

function RowNote({ note }) {
  if (!note) return null;
  return (
    <div style={{ fontSize: 11.5, lineHeight: 1.5, color: note.error ? C.danger : C.amber, padding: "2px 0 4px" }}>
      {note.msg}
    </div>
  );
}

function McpChip({ dark }) {
  return (
    <code style={{
      fontFamily: mono, fontSize: 12, borderRadius: 4, padding: "2px 6px",
      background: dark ? D.chipCodeBg : D.toastChipBg,
      color: dark ? D.chipCodeText : D.toastChipText,
    }}>/mcp</code>
  );
}

// --- Header + toolbar --------------------------------------------------------

function StatusPill({ connected }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6, borderRadius: 999, padding: "3px 10px",
      background: connected ? C.okBg : C.subtle,
      border: `1px solid ${connected ? C.okBorder : C.inputBorder}`,
    }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: connected ? C.ok : C.t3, display: "inline-block" }} />
      <span style={{ fontSize: 11.5, fontWeight: 600, color: connected ? C.ok : C.t3 }}>
        {connected ? "Connected" : "Not connected"}
      </span>
    </span>
  );
}

function SearchField({ value, onChange, inputRef }) {
  const [focused, setFocused] = useState(false);
  return (
    <div style={{
      flex: 1, minWidth: 220, maxWidth: 330, height: 34, boxSizing: "border-box",
      display: "flex", alignItems: "center", gap: 8, padding: "0 9px",
      background: "#fff", border: `1px solid ${focused ? C.borderStrong : C.inputBorder}`,
      borderRadius: 8, transition: "border-color .12s",
    }}>
      <span style={{ color: C.tLabel, display: "inline-flex" }}><MagnifierIcon /></span>
      <input ref={inputRef} value={value} onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        placeholder="Search commands and resources"
        onKeyDown={(e) => { if (e.key === "Escape") { onChange(""); e.target.blur(); } }}
        style={{ all: "unset", flex: 1, minWidth: 0, fontSize: 13, fontFamily: SANS, color: C.ink }} />
      {value ? (
        <button onClick={() => onChange("")} title="Clear search"
          style={{ all: "unset", cursor: "pointer", color: C.t3, fontSize: 13, lineHeight: 1, padding: "0 2px" }}>✕</button>
      ) : (
        <span style={{ fontFamily: mono, fontSize: 11, color: C.faint, border: `1px solid ${C.borderInner}`, borderRadius: 4, padding: "1px 5px" }}>/</span>
      )}
    </div>
  );
}

function Segmented({ value, onChange, options }) {
  return (
    <div style={{ display: "inline-flex", alignItems: "center", background: D.segBg, borderRadius: 8, padding: 3, gap: 2, flexShrink: 0 }}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <SegBtn key={o.value} on={on} onClick={() => onChange(o.value)} label={o.label} count={o.count} />
        );
      })}
    </div>
  );
}

function SegBtn({ on, onClick, label, count }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick}
      style={{
        all: "unset", cursor: "pointer", borderRadius: 6, padding: "5px 11px",
        fontSize: 12.5, fontWeight: on ? 600 : 500, fontFamily: SANS,
        background: on ? "#fff" : "transparent",
        color: on ? C.ink : h ? C.ink : C.tMuted,
        boxShadow: on ? "0 1px 2px rgba(28,27,25,.14)" : "none",
        transition: "color .12s", whiteSpace: "nowrap",
      }}>
      {label} <span style={{ color: on ? C.tLabel : "inherit", fontWeight: 500 }}>({count})</span>
    </button>
  );
}

function TypeChip({ on, onClick, label, count }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick}
      style={{
        all: "unset", cursor: "pointer", borderRadius: 999, padding: "5px 13px",
        fontSize: 12.5, fontFamily: SANS, whiteSpace: "nowrap",
        background: on ? D.darkChip : h ? C.soft : "transparent",
        border: `1px solid ${on ? D.darkChip : C.inputBorder}`,
        color: on ? D.darkChipText : C.tMuted,
        fontWeight: on ? 600 : 500, transition: "all .12s",
      }}>
      {label} <span style={{ color: on ? D.darkChipCount : "inherit", fontWeight: 500 }}>({count})</span>
    </button>
  );
}

function DescToggle({ on, onClick }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick}
      style={{ all: "unset", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 8, opacity: h ? 0.75 : 1, flexShrink: 0 }}>
      <span style={{ fontSize: 13, fontFamily: SANS, color: on ? C.t2 : C.tMuted }}>Descriptions</span>
      <span style={{
        width: 34, height: 20, borderRadius: 999, position: "relative", display: "inline-block",
        background: on ? "#5c5548" : C.disabled, transition: "background .15s",
      }}>
        <span style={{
          position: "absolute", top: 3, left: on ? 17 : 3, width: 14, height: 14,
          borderRadius: "50%", background: "#fff", transition: "left .15s",
        }} />
      </span>
    </button>
  );
}

// --- Rows --------------------------------------------------------------------

function RefLine({ prefix, name, suffix }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", minWidth: 0, whiteSpace: "nowrap" }}>
      {prefix && <span style={{ fontFamily: mono, fontSize: 13.5, color: C.t3, overflow: "hidden", textOverflow: "ellipsis", flexShrink: 1, minWidth: 0 }}>{prefix}</span>}
      <span style={{ fontFamily: mono, fontSize: 15.5, fontWeight: 700, color: C.ink, letterSpacing: "-.005em", overflow: "hidden", textOverflow: "ellipsis" }}>{name}</span>
      {suffix && <span style={{ fontFamily: mono, fontSize: 13.5, color: C.t3, flexShrink: 0 }}>{suffix}</span>}
    </div>
  );
}

function RenameEditor({ prefix, draft, setDraft, onSave, onCancel }) {
  const savedRef = useRef(false);
  const save = () => { if (savedRef.current) return; savedRef.current = true; onSave(); };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0, flexWrap: "wrap" }}>
      {prefix && <span style={{ fontFamily: mono, fontSize: 13.5, color: C.tMuted, flexShrink: 0 }}>{prefix}</span>}
      <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); save(); }
          if (e.key === "Escape") { e.preventDefault(); onCancel(); }
        }}
        onFocus={(e) => { e.target.style.borderColor = C.accent; e.target.style.boxShadow = "0 0 0 3px rgba(194,96,58,0.14)"; }}
        onBlur={(e) => { e.target.style.borderColor = C.inputBorder; e.target.style.boxShadow = "none"; }}
        style={{
          outline: "none", flex: 1, minWidth: 140, fontFamily: mono, fontSize: 15, fontWeight: 700,
          background: "#fff", border: `1px solid ${C.inputBorder}`, borderRadius: 6, padding: "4px 9px",
          transition: "border-color .12s, box-shadow .12s", color: C.ink,
        }} />
      <button onClick={save}
        style={{ all: "unset", cursor: "pointer", background: C.accent, color: "#fff7f2", borderRadius: 6, padding: "5px 12px", fontSize: 12, fontWeight: 600, fontFamily: SANS }}>
        Save
      </button>
      <button onClick={onCancel}
        style={{ all: "unset", cursor: "pointer", border: `1px solid ${C.inputBorder}`, color: C.t2, borderRadius: 6, padding: "4px 11px", fontSize: 12, fontFamily: SANS }}>
        Cancel
      </button>
    </div>
  );
}

function ItemRow({ first, refParts, copyValue, description, sourcePath, locked, effective, template, descOn,
  disabled, busy, note, copied, onCopy, onToggle, editing, onStartEdit, editDraft, setEditDraft, onSaveEdit, onCancelEdit }) {
  const [h, hp] = useHover();
  return (
    <div {...hp} style={{ borderTop: first ? "none" : `1px solid ${C.borderRow}`, background: h ? C.subtle : "transparent", transition: "background .1s" }}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) auto auto", alignItems: "center", gap: 14, padding: "8px 14px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 3, minWidth: 0 }}>
          {editing ? (
            <RenameEditor prefix={refParts.prefix} draft={editDraft} setDraft={setEditDraft} onSave={onSaveEdit} onCancel={onCancelEdit} />
          ) : (
            <RefLine prefix={refParts.prefix} name={refParts.name} suffix={refParts.suffix} />
          )}
          {descOn && description && (
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.4, color: C.tMuted, maxWidth: "76ch", fontFamily: SANS }}>{description}</p>
          )}
          {descOn && sourcePath && (
            <span style={{ fontFamily: mono, fontSize: 11.5, color: C.faint }}>{sourcePath}</span>
          )}
          <RowNote note={note} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
          {copyValue && (copied ? (
            <span style={{ fontSize: 11.5, fontWeight: 600, color: C.ok, whiteSpace: "nowrap", padding: "0 2px", fontFamily: SANS }}>✓ Copied</span>
          ) : (
            <IconBtn title="Copy full reference" onClick={() => onCopy(copyValue)}><CopyIcon /></IconBtn>
          ))}
          {!locked && !editing && onStartEdit && (
            <IconBtn title="Rename" onClick={onStartEdit}><PencilIcon /></IconBtn>
          )}
          {template && (
            <span title="One toggle controls the template; every generated entry follows it."
              style={{ fontFamily: mono, fontSize: 9.5, fontWeight: 600, padding: "2px 7px", borderRadius: 20, color: C.t3, background: C.subtle, border: `1px solid ${C.inputBorder}`, whiteSpace: "nowrap" }}>
              template
            </span>
          )}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
          {locked ? (
            <span style={{ fontSize: 12, color: C.t3, whiteSpace: "nowrap", fontFamily: SANS }}>Always listed</span>
          ) : (
            <Switch on={effective} disabled={disabled || busy} onClick={onToggle}
              title={effective ? "Listed in picker — click to hide" : "Hidden from picker — click to list"} />
          )}
        </div>
      </div>
    </div>
  );
}

// --- Group + section chrome --------------------------------------------------

function BulkBtn({ label, onClick, tone }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick}
      style={{
        all: "unset", cursor: "pointer", fontSize: 12, fontFamily: SANS, padding: "3px 8px", borderRadius: 6,
        color: h ? (tone === "on" ? C.ok : C.ink) : C.t3,
        background: h ? C.soft : "transparent", transition: "all .12s", whiteSpace: "nowrap",
      }}>
      {label}
    </button>
  );
}

function GroupCard({ name, meta, open, onToggleOpen, bulk, children }) {
  const [h, hp] = useHover();
  return (
    <div style={{ background: "#fff", border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: C.soft }}>
        <button {...hp} onClick={onToggleOpen}
          style={{ all: "unset", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 8, minWidth: 0, opacity: h ? 0.7 : 1 }}>
          <Caret open={open} size={10} color={C.t3} />
          <span style={{ fontFamily: mono, fontSize: 15, fontWeight: 700, color: C.ink, letterSpacing: "-.01em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
        </button>
        <span style={{ flex: 1 }} />
        {bulk && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 2, flexShrink: 0 }}>
            <BulkBtn label="List all" tone="on" onClick={bulk.onAll} />
            <span style={{ color: C.faint, fontSize: 11 }}>·</span>
            <BulkBtn label="Hide all" onClick={bulk.onNone} />
          </span>
        )}
        <span style={{ fontFamily: mono, fontSize: 11.5, color: C.t3, whiteSpace: "nowrap", flexShrink: 0 }}>{meta}</span>
      </div>
      {open && <div style={{ borderTop: `1px solid ${C.borderInner}` }}>{children}</div>}
    </div>
  );
}

function SectionHeader({ label, summary, open, onToggleOpen }) {
  const [h, hp] = useHover();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 10 }}>
      <button {...hp} onClick={onToggleOpen}
        style={{ all: "unset", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
        <Caret open={open} />
        <span style={{ fontFamily: mono, fontSize: 13, fontWeight: 650, letterSpacing: ".09em", textTransform: "uppercase", color: h ? C.accent : C.ink, transition: "color .12s" }}>{label}</span>
      </button>
      <span style={{ fontSize: 13, color: C.tLabel, whiteSpace: "nowrap", fontFamily: SANS, flexShrink: 0 }}>{summary}</span>
      <span style={{ flex: 1, height: 1, background: C.divider }} />
    </div>
  );
}

// --- Pending bar + toast -----------------------------------------------------

function BarGhostBtn({ children, onClick, disabled }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick} disabled={disabled}
      style={{
        all: "unset", cursor: disabled ? "default" : "pointer", border: `1px solid ${D.barGhostBorder}`,
        color: D.barGhostText, borderRadius: 8, padding: "7px 13px", fontSize: 12.5, fontFamily: SANS,
        background: h && !disabled ? D.barGhostHover : "transparent", transition: "background .12s", whiteSpace: "nowrap",
        opacity: disabled ? 0.6 : 1,
      }}>
      {children}
    </button>
  );
}

function PendingBar({ count, onDiscard, onReload, busy }) {
  const [h, hp] = useHover();
  return (
    <div style={{
      position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 30,
      maxWidth: 880, width: "calc(100% - 48px)", boxSizing: "border-box",
      background: D.barBg, color: D.barText, borderRadius: 12, padding: "11px 12px 11px 20px",
      boxShadow: "0 12px 32px rgba(35,31,25,0.35)",
      display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
    }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: D.amberDot, flexShrink: 0 }} />
      <span style={{ fontSize: 13.5, fontWeight: 600, fontFamily: SANS, whiteSpace: "nowrap" }}>
        {count} pending change{count === 1 ? "" : "s"}
      </span>
      <span style={{ fontSize: 13, color: D.barMuted, fontFamily: SANS, flex: 1, minWidth: 180 }}>
        Reload, then run <McpChip dark /> in Claude Code to reconnect
      </span>
      <span style={{ width: 1, alignSelf: "stretch", background: D.barDivider, flexShrink: 0 }} />
      <BarGhostBtn onClick={onDiscard} disabled={busy}>Discard</BarGhostBtn>
      <button {...hp} onClick={onReload} disabled={busy}
        style={{
          all: "unset", cursor: busy ? "default" : "pointer", background: h && !busy ? "#fff" : D.barBtnBg,
          color: D.barBtnText, borderRadius: 8, padding: "7px 15px", fontSize: 12.5, fontWeight: 650,
          fontFamily: SANS, transition: "background .12s", whiteSpace: "nowrap", opacity: busy ? 0.7 : 1,
        }}>
        {busy ? "Reloading…" : "Reload server"}
      </button>
    </div>
  );
}

function ReloadedToast({ onDismiss }) {
  const [h, hp] = useHover();
  return (
    <div style={{
      position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 30,
      background: D.toastBg, color: D.toastText, borderRadius: 12, padding: "11px 16px 11px 20px",
      boxShadow: "0 12px 32px rgba(35,31,25,0.35)",
      display: "flex", alignItems: "center", gap: 12, maxWidth: 880,
    }}>
      <span style={{ fontSize: 13.5, fontWeight: 600, fontFamily: SANS, whiteSpace: "nowrap" }}>✓ Server reloaded</span>
      <span style={{ fontSize: 13, color: D.toastMuted, fontFamily: SANS }}>
        Run <McpChip /> in Claude Code to reconnect
      </span>
      <button {...hp} onClick={onDismiss} title="Dismiss"
        style={{ all: "unset", cursor: "pointer", color: h ? "#fff" : D.toastX, fontSize: 14, lineHeight: 1, padding: "0 2px" }}>✕</button>
    </div>
  );
}

// --- Grouping (unchanged data shape) -----------------------------------------

function buildGroups(data) {
  const ORDER = [
    { key: "agents", label: "Agents", noun: "agents" },
    { key: "modules", label: "Modules", noun: "modules" },
    { key: "connections", label: "Connections", noun: "connections" },
    { key: "framework", label: "Framework", noun: "groups" },
  ];

  const groupMap = {};

  for (const res of (data.resources || [])) {
    const kind = res.kind;
    const folderName = res.key.slice(kind.length + 1);
    if (!groupMap[kind]) groupMap[kind] = {};
    if (!groupMap[kind][folderName]) groupMap[kind][folderName] = { name: folderName, resource: null, commands: [] };
    groupMap[kind][folderName].resource = res;
  }

  for (const cmd of (data.commands || [])) {
    const cat = cmd.category;
    if (!cat) continue;
    const folderName = cmd.owner;
    if (!groupMap[cat]) groupMap[cat] = {};
    if (!groupMap[cat][folderName]) groupMap[cat][folderName] = { name: folderName, resource: null, commands: [] };
    groupMap[cat][folderName].commands.push(cmd);
  }

  for (const cat of Object.values(groupMap)) {
    for (const folder of Object.values(cat)) {
      folder.commands.sort((a, b) => {
        if (a.template && !b.template) return -1;
        if (!a.template && b.template) return 1;
        return (a.default_name || a.name).localeCompare(b.default_name || b.name);
      });
    }
  }

  return ORDER
    .map(({ key, label, noun }) => {
      const folders = Object.values(groupMap[key] || {}).sort((a, b) => a.name.localeCompare(b.name));
      if (folders.length === 0) return null;
      return { key, label, noun, folders };
    })
    .filter(Boolean);
}

// --- Main --------------------------------------------------------------------

export default function Controls() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const [notes, setNotes] = useState({});
  const [sessions, setSessions] = useState([]);

  // Pending model: baseline = committed server state at load / last reload.
  // Every write still commits to controls.yaml immediately; "pending" is the
  // diff against the baseline, so off-and-back-on nets to zero.
  const [baseline, setBaseline] = useState(null);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [collapsedSections, setCollapsedSections] = useState(() => new Set());
  const [collapsedGroups, setCollapsedGroups] = useState(() => new Set());
  const [descOn, setDescOn] = useState(() => localStorage.getItem("gc.controls.desc") !== "0");

  const [editingKey, setEditingKey] = useState(null);
  const [editDraft, setEditDraft] = useState("");
  const [copiedKey, setCopiedKey] = useState(null);
  const [toast, setToast] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [discarding, setDiscarding] = useState(false);

  const [addingPin, setAddingPin] = useState(false);
  const [pinDraft, setPinDraft] = useState("");
  const [pinError, setPinError] = useState(null);

  const searchRef = useRef(null);
  const copyTimer = useRef(null);
  const toastTimer = useRef(null);
  const mobile = useIsMobile();

  const snapshot = (d) => {
    const eff = {}, name = {}, revert = {};
    for (const c of (d.commands || [])) {
      eff[c.key] = c.effective;
      name[c.key] = c.name;
      revert[c.key] = c.custom ? c.name : "";
    }
    return { eff, name, revert };
  };

  const load = (resetBaseline) => {
    getJSON("/api/controls").then((d) => {
      setData(d);
      setErr(null);
      if (resetBaseline) setBaseline(snapshot(d));
      else setBaseline((b) => b || snapshot(d));
    }).catch((e) => setErr(e.message));
  };
  useEffect(() => {
    load(false);
    getJSON("/api/sessions").then((d) => setSessions(d.sessions || [])).catch(() => {});
  }, []);

  // "/" focuses the search field from anywhere outside an input.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = e.target && e.target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || (e.target && e.target.isContentEditable)) return;
      e.preventDefault();
      searchRef.current && searchRef.current.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => () => { clearTimeout(copyTimer.current); clearTimeout(toastTimer.current); }, []);

  const hideToast = () => { clearTimeout(toastTimer.current); setToast(false); };

  const post = (rowKey, body) => {
    setBusyKey(rowKey);
    hideToast();
    return postJSON("/api/controls", body)
      .then((d) => {
        const { note, ...rest } = d;
        setData(rest);
        setErr(null);
        setNotes((n) => ({ ...n, [rowKey]: note ? { msg: note } : null }));
      })
      .catch((e) => {
        setNotes((n) => ({ ...n, [rowKey]: { msg: e.message, error: true } }));
        load(false);
      })
      .finally(() => setBusyKey(null));
  };

  const setCommand = (key, value) => post(key, { section: "commands", key, value });
  const setResource = (key, value) => post(key, { section: "resources", key, value });
  const rename = (key, value) => post(key, { name: { key, value } });
  const bulkToggle = (owner, value) => post("bulk:" + owner, { bulk: { owner, value } });
  const unpin = (path) => post("pin:" + path, { pin: path, pinned: false });

  const submitPin = () => {
    const path = pinDraft.trim();
    if (!path) return;
    const key = "pin:" + path;
    setPinError(null);
    setBusyKey(key);
    postJSON("/api/controls", { pin: path, pinned: true })
      .then((d) => {
        const { note, ...rest } = d;
        setData(rest);
        setErr(null);
        setNotes((n) => ({ ...n, [key]: note ? { msg: note } : null }));
        setAddingPin(false);
        setPinDraft("");
      })
      .catch((e) => { setPinError(e.message); load(false); })
      .finally(() => setBusyKey(null));
  };

  // --- Rename editing --------------------------------------------------------
  const startEdit = (key, currentName) => { setEditingKey(key); setEditDraft(currentName); };
  const cancelEdit = () => { setEditingKey(null); setEditDraft(""); };
  const saveEdit = (item) => {
    const key = editingKey;
    cancelEdit();
    const trimmed = editDraft.trim();
    if (!trimmed) return; // empty draft reverts to the previous name
    const value = trimmed === item.default_name ? "" : trimmed;
    const current = item.custom ? item.name : "";
    if (value === current) return;
    rename(key, value);
  };

  // --- Copy ------------------------------------------------------------------
  const doCopy = (key, text) => {
    copyText(text);
    clearTimeout(copyTimer.current);
    setCopiedKey(key);
    copyTimer.current = setTimeout(() => setCopiedKey(null), 1500);
  };

  // --- Pending / reload / discard --------------------------------------------
  const pending = useMemo(() => {
    if (!data || !baseline) return [];
    const diffs = [];
    for (const c of (data.commands || [])) {
      if (baseline.eff[c.key] !== undefined && baseline.eff[c.key] !== c.effective) {
        diffs.push({ kind: "toggle", key: c.key, to: baseline.eff[c.key] ? "on" : "off" });
      }
      if (baseline.name[c.key] !== undefined && baseline.name[c.key] !== c.name) {
        diffs.push({ kind: "rename", key: c.key, to: baseline.revert[c.key] });
      }
    }
    return diffs;
  }, [data, baseline]);

  const doReload = () => {
    setReloading(true);
    postJSON("/api/reload", {})
      .then(() => {
        load(true);
        setToast(true);
        clearTimeout(toastTimer.current);
        toastTimer.current = setTimeout(() => setToast(false), 6000);
      })
      .catch((e) => setErr(e.message))
      .finally(() => setReloading(false));
  };

  const doDiscard = async () => {
    setDiscarding(true);
    try {
      for (const d of pending) {
        const body = d.kind === "toggle"
          ? { section: "commands", key: d.key, value: d.to }
          : { name: { key: d.key, value: d.to } };
        await postJSON("/api/controls", body);
      }
      load(false);
    } catch (e) {
      setErr(e.message);
      load(false);
    } finally {
      setDiscarding(false);
    }
  };

  // --- Early exits -----------------------------------------------------------
  if (err && !data) return <div style={{ color: C.danger, fontSize: 13.5, padding: 20 }}>Could not load: {err}</div>;
  if (!data && !err) return <div style={{ padding: "60px 0", textAlign: "center", color: C.t3, fontSize: 14 }}>Loading...</div>;

  const disabled = !!err;
  const busy = reloading || discarding;

  // --- Catalog + counts ------------------------------------------------------
  const structural = data.structural || [];
  const resources = data.resources || [];
  const commands = data.commands || [];
  const groups = buildGroups(data);

  const totalCount = structural.length + resources.length + commands.length;
  const listedCount = structural.length + resources.filter((r) => r.effective).length + commands.filter((c) => c.effective).length;
  const resourceCount = structural.length + resources.length;
  const commandCount = commands.length;

  // --- Filtering -------------------------------------------------------------
  const q = query.trim().toLowerCase();
  const filtering = !!q || statusFilter !== "all" || typeFilter !== "all";

  const matches = (texts) => !q || texts.some((t) => (t || "").toLowerCase().includes(q));
  const nMatches = (n) => `${n} match${n === 1 ? "" : "es"}`;
  const statusOk = (listed) => statusFilter === "all" || (statusFilter === "listed" ? listed : !listed);
  const typeOk = (kind) => typeFilter === "all" || typeFilter === kind;

  const cmdVisible = (cmd, groupName) =>
    typeOk("command") && statusOk(cmd.effective) &&
    matches([commandPrefix() + cmd.name, cmd.name, groupName, cmd.description, cmd.path]);
  const resVisible = (res, groupName) =>
    typeOk("resource") && statusOk(res.effective) &&
    matches([fileRef(res.key + "/index.md"), res.name, groupName, res.description]);
  const structVisible = (row) =>
    typeOk("resource") && statusOk(true) &&
    matches([row.name, row.description, row.path, row.path ? fileRef(row.path) : ""]);
  const pinVisible = (path) =>
    typeOk("resource") && statusOk(true) && matches([path, fileRef(path)]);

  const visibleStructural = structural.filter(structVisible);
  const visiblePins = (data.pinned || []).filter(pinVisible);

  const visibleGroups = groups.map((section) => {
    const folders = section.folders.map((folder) => {
      const res = folder.resource && resVisible(folder.resource, folder.name) ? folder.resource : null;
      const cmds = folder.commands.filter((c) => cmdVisible(c, folder.name));
      return { ...folder, visibleResource: res, visibleCommands: cmds, matchCount: (res ? 1 : 0) + cmds.length };
    }).filter((f) => !filtering || f.matchCount > 0);
    const matchCount = folders.reduce((n, f) => n + f.matchCount, 0);
    return { ...section, visibleFolders: folders, matchCount };
  }).filter((s) => !filtering || s.matchCount > 0);

  const anyVisible = visibleStructural.length > 0 || visiblePins.length > 0 || visibleGroups.length > 0;

  const sectionOpen = (id) => filtering || !collapsedSections.has(id);
  const groupOpen = (id) => filtering || !collapsedGroups.has(id);
  const toggleSet = (set, id) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  };

  const clearFilters = () => { setQuery(""); setStatusFilter("all"); setTypeFilter("all"); };

  // --- Row renderers ---------------------------------------------------------
  const renderCommand = (cmd, first) => (
    <ItemRow key={cmd.key} first={first}
      refParts={{ prefix: commandPrefix(), name: cmd.name }}
      copyValue={commandInvocation(cmd.name)}
      description={cmd.description} sourcePath={cmd.path}
      effective={cmd.effective} template={cmd.template} descOn={descOn}
      disabled={disabled || busy} busy={busyKey === cmd.key} note={notes[cmd.key]}
      copied={copiedKey === cmd.key} onCopy={(v) => doCopy(cmd.key, v)}
      onToggle={() => setCommand(cmd.key, cmd.effective ? "off" : "on")}
      editing={editingKey === cmd.key}
      onStartEdit={() => startEdit(cmd.key, cmd.name)}
      editDraft={editDraft} setEditDraft={setEditDraft}
      onSaveEdit={() => saveEdit(cmd)} onCancelEdit={cancelEdit} />
  );

  const renderResource = (res, first) => (
    <ItemRow key={res.key} first={first}
      refParts={{ prefix: fileRef(res.kind + "/"), name: res.name, suffix: "/index.md" }}
      copyValue={fileRef(res.key + "/index.md")}
      description={res.description} sourcePath=""
      effective={res.effective} descOn={descOn}
      disabled={disabled || busy} busy={busyKey === res.key} note={notes[res.key]}
      copied={copiedKey === res.key} onCopy={(v) => doCopy(res.key, v)}
      onToggle={() => setResource(res.key, res.effective ? "off" : "on")}
      editing={editingKey === res.key}
      onStartEdit={() => startEdit(res.key, res.custom ? res.name : res.default_name)}
      editDraft={editDraft} setEditDraft={setEditDraft}
      onSaveEdit={() => saveEdit(res)} onCancelEdit={cancelEdit} />
  );

  const serverName = getServerName();
  const connected = (sessions || []).length > 0;

  return (
    <div style={{ paddingBottom: pending.length > 0 || toast ? 90 : 0, fontFamily: SANS }}>
      {/* Sticky header */}
      <div style={{
        position: "sticky", top: 0, zIndex: 10,
        background: "rgba(239,236,232,0.94)", backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
        borderBottom: `1px solid ${C.divider}`,
        margin: mobile ? "-16px -14px 0" : "-22px -30px 0",
        padding: mobile ? "14px 14px 12px" : "18px 30px 14px",
        display: "flex", flexDirection: "column", gap: 14,
      }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 14, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 650, letterSpacing: ".12em", textTransform: "uppercase", color: C.tLabel, marginBottom: 3 }}>MCP Server</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontFamily: mono, fontSize: 21, fontWeight: 600, letterSpacing: "-.01em", color: C.ink }}>{serverName}</span>
              <StatusPill connected={connected} />
            </div>
          </div>
          <div style={{ fontSize: 13, color: C.tMuted, paddingBottom: 2 }}>
            <strong style={{ color: C.ink, fontWeight: 650 }}>{listedCount}</strong> of {totalCount} listed in picker
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <SearchField value={query} onChange={setQuery} inputRef={searchRef} />
          <Segmented value={statusFilter} onChange={setStatusFilter} options={[
            { value: "all", label: "All", count: totalCount },
            { value: "listed", label: "Listed", count: listedCount },
            { value: "hidden", label: "Hidden", count: totalCount - listedCount },
          ]} />
          <TypeChip on={typeFilter === "resource"} label="Resources" count={resourceCount}
            onClick={() => setTypeFilter(typeFilter === "resource" ? "all" : "resource")} />
          <TypeChip on={typeFilter === "command"} label="Commands" count={commandCount}
            onClick={() => setTypeFilter(typeFilter === "command" ? "all" : "command")} />
          <span style={{ flex: 1 }} />
          <DescToggle on={descOn} onClick={() => {
            const next = !descOn;
            setDescOn(next);
            localStorage.setItem("gc.controls.desc", next ? "1" : "0");
          }} />
        </div>
      </div>

      {err && (
        <div style={{ margin: "18px 0 0", background: C.missFill, border: `1px solid ${C.missBorder}`, color: C.missText, borderRadius: 7, padding: "11px 13px", fontSize: 13, lineHeight: 1.5 }}>
          {err}. Toggles and editors are disabled until the file parses. Fix controls.yaml by hand and refresh.
        </div>
      )}

      <div style={{ paddingTop: 22, display: "flex", flexDirection: "column", gap: 24 }}>
        {!anyVisible && filtering ? (
          <div style={{ background: "#fff", border: `1px dashed ${C.borderStrong}`, borderRadius: 12, padding: "44px 32px", textAlign: "center" }}>
            <div style={{ fontSize: 14.5, fontWeight: 650, color: C.t2, marginBottom: 4 }}>No matches</div>
            <div style={{ fontSize: 13, color: C.tMuted, marginBottom: 16 }}>Nothing matches the current search and filters.</div>
            <GhostBtn onClick={clearFilters}>Clear filters</GhostBtn>
          </div>
        ) : (
          <>
            {(!filtering || visibleStructural.length > 0) && (
              <div>
                <SectionHeader label="Built-in"
                  summary={filtering ? nMatches(visibleStructural.length) : `${structural.length} items · always listed`}
                  open={sectionOpen("built-in")}
                  onToggleOpen={() => setCollapsedSections((s) => toggleSet(s, "built-in"))} />
                {sectionOpen("built-in") && (
                  <div style={{ background: "#fff", border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
                    {visibleStructural.length === 0 ? (
                      <EmptyState style={{ margin: 12, border: "none" }}>No built-in resources.</EmptyState>
                    ) : visibleStructural.map((row, i) => (
                      <ItemRow key={"structural:" + row.key} first={i === 0}
                        refParts={{ prefix: "", name: row.name }}
                        copyValue={row.path ? fileRef(row.path) : null}
                        description={row.description} sourcePath={row.path}
                        locked descOn={descOn}
                        disabled busy={false} note={null}
                        copied={copiedKey === "structural:" + row.key}
                        onCopy={(v) => doCopy("structural:" + row.key, v)} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {visibleGroups.map((section) => (
              <div key={section.key}>
                <SectionHeader label={section.label}
                  summary={filtering
                    ? nMatches(section.matchCount)
                    : `${section.folders.length} ${section.noun} · ${sectionListed(section)} of ${sectionTotal(section)} listed`}
                  open={sectionOpen(section.key)}
                  onToggleOpen={() => setCollapsedSections((s) => toggleSet(s, section.key))} />
                {sectionOpen(section.key) && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {section.visibleFolders.map((folder) => {
                      const gid = section.key + "/" + folder.name;
                      const total = (folder.resource ? 1 : 0) + folder.commands.length;
                      const listed = (folder.resource && folder.resource.effective ? 1 : 0) + folder.commands.filter((c) => c.effective).length;
                      return (
                        <GroupCard key={folder.name} name={folder.name}
                          meta={`${listed} of ${total} listed`}
                          open={groupOpen(gid)}
                          onToggleOpen={() => setCollapsedGroups((s) => toggleSet(s, gid))}
                          bulk={folder.commands.length > 1 ? {
                            onAll: () => bulkToggle(folder.name, "on"),
                            onNone: () => bulkToggle(folder.name, "off"),
                          } : null}>
                          {folder.visibleResource && renderResource(folder.visibleResource, true)}
                          {folder.visibleCommands.map((c, i) => renderCommand(c, !folder.visibleResource && i === 0))}
                        </GroupCard>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}

            {(!filtering || visiblePins.length > 0) && (
              <div>
                <SectionHeader label="Pinned files"
                  summary={filtering ? nMatches(visiblePins.length) : `${(data.pinned || []).length} pinned · always listed`}
                  open={sectionOpen("pinned")}
                  onToggleOpen={() => setCollapsedSections((s) => toggleSet(s, "pinned"))} />
                {sectionOpen("pinned") && (
                  <div style={{ background: "#fff", border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
                    {visiblePins.map((p, i) => (
                      <div key={p} style={{ borderTop: i === 0 ? "none" : `1px solid ${C.borderRow}` }}>
                        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) auto auto", alignItems: "center", gap: 14, padding: "8px 14px" }}>
                          <div style={{ minWidth: 0 }}>
                            <RefLine prefix={`@${serverName}:gcontext://`} name={p} />
                            <RowNote note={notes["pin:" + p]} />
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
                            {copiedKey === "pin:" + p ? (
                              <span style={{ fontSize: 11.5, fontWeight: 600, color: C.ok, whiteSpace: "nowrap", padding: "0 2px" }}>✓ Copied</span>
                            ) : (
                              <IconBtn title="Copy full reference" onClick={() => doCopy("pin:" + p, fileRef(p))}><CopyIcon /></IconBtn>
                            )}
                          </div>
                          <PinUnpinBtn disabled={disabled || busy || busyKey === "pin:" + p} onClick={() => unpin(p)} />
                        </div>
                      </div>
                    ))}
                    {!filtering && (
                      <div style={{ borderTop: (data.pinned || []).length > 0 ? `1px solid ${C.borderRow}` : "none", padding: "10px 14px" }}>
                        {addingPin ? (
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <Field value={pinDraft} onChange={(e) => setPinDraft(e.target.value)}
                              placeholder="modules/<name>/path.md"
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { e.preventDefault(); submitPin(); }
                                if (e.key === "Escape") { e.preventDefault(); setAddingPin(false); setPinDraft(""); setPinError(null); }
                              }}
                              autoFocus
                              style={{ flex: 1, fontFamily: mono, fontSize: 12.5, padding: "6px 9px" }} />
                            <GhostBtn onClick={submitPin}>Add</GhostBtn>
                            <GhostBtn onClick={() => { setAddingPin(false); setPinDraft(""); setPinError(null); }}>Cancel</GhostBtn>
                          </div>
                        ) : (
                          <GhostBtn onClick={() => { setAddingPin(true); setPinError(null); }}>Add pin</GhostBtn>
                        )}
                        {pinError && <RowNote note={{ msg: pinError, error: true }} />}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {(data.stale || []).length > 0 && !filtering && (
              <p style={{ margin: 0, fontSize: 12, color: C.t3, lineHeight: 1.6 }}>
                Entries with no matching file on disk (kept in controls.yaml, delete the lines by hand if stale):{" "}
                {data.stale.map((s) => s.key).join(", ")}
              </p>
            )}
          </>
        )}
      </div>

      {toast ? (
        <ReloadedToast onDismiss={hideToast} />
      ) : pending.length > 0 ? (
        <PendingBar count={pending.length} onDiscard={doDiscard} onReload={doReload} busy={busy} />
      ) : null}
    </div>
  );
}

function sectionTotal(section) {
  return section.folders.reduce((n, f) => n + (f.resource ? 1 : 0) + f.commands.length, 0);
}

function sectionListed(section) {
  return section.folders.reduce((n, f) =>
    n + (f.resource && f.resource.effective ? 1 : 0) + f.commands.filter((c) => c.effective).length, 0);
}

function PinUnpinBtn({ disabled, onClick }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick} disabled={disabled} title="Unpin"
      style={{ all: "unset", cursor: disabled ? "default" : "pointer", fontSize: 12, fontWeight: 600, color: h ? C.danger : C.t3, padding: "3px 8px", borderRadius: 6, background: h ? C.soft : "transparent", transition: "all .12s", justifySelf: "end" }}>
      Unpin
    </button>
  );
}
