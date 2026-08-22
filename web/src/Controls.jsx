import React, { useEffect, useRef, useState } from "react";
import { getJSON, postJSON, commandInvocation, fileRef } from "./lib.js";
import { C, mono, Chip, cardBase, pageTitle, sectionLabel, EmptyState, useHover, GhostBtn, FileGlyph } from "./ui.jsx";
import CopyPrompt from "./Copy.jsx";

// Controls: the on/off registry (controls.yaml) as toggles + rename editors.
// Every toggle writes one line through POST /api/controls; the file stays the
// source of truth and hand edits keep working. Template (each:) files get one
// toggle for the whole template; per-entry overrides stay hand edits.

// ---- primitives ----

function Switch({ on, disabled, onClick, title }) {
  return (
    <button onClick={onClick} disabled={disabled} title={title} aria-pressed={on}
      style={{ all: "unset", boxSizing: "border-box", cursor: disabled ? "default" : "pointer", width: 32, height: 18, borderRadius: 10, background: on ? C.ok : C.faint, position: "relative", transition: "background .15s", flexShrink: 0, opacity: disabled ? 0.45 : 1 }}>
      <span style={{ position: "absolute", top: 2, left: on ? 16 : 2, width: 14, height: 14, borderRadius: "50%", background: "#fff", boxShadow: "0 1px 2px rgba(28,27,25,.25)", transition: "left .15s" }} />
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

function TerminalGlyph() {
  return (
    <span style={{ width: 26, height: 20, flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center", background: C.codeBg, color: C.onDark, borderRadius: 4, fontFamily: mono, fontSize: 10, fontWeight: 700, letterSpacing: "-.02em" }}>&gt;_</span>
  );
}

// ---- NameEditor: inline rename with pencil icon ----

function NameEditor({ name, customName, rowKey, disabled, onSave }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const savedRef = useRef(false);

  const startEdit = () => {
    if (disabled) return;
    setDraft(customName || name);
    savedRef.current = false;
    setEditing(true);
  };

  const save = () => {
    if (savedRef.current) return;
    savedRef.current = true;
    setEditing(false);
    const trimmed = draft.trim();
    // empty save clears the override
    const value = trimmed === name ? "" : trimmed;
    // skip no-op: clearing when there is no custom name, or same custom name
    if (!value && !customName) return;
    if (value === customName) return;
    onSave(rowKey, value);
  };

  const cancel = () => setEditing(false);

  const onKeyDown = (e) => {
    if (e.key === "Enter") { e.preventDefault(); save(); }
    if (e.key === "Escape") { e.preventDefault(); cancel(); }
  };

  if (editing) {
    return (
      <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown} onBlur={save}
        style={{ outline: "none", fontFamily: mono, fontSize: 13, fontWeight: 600, padding: "2px 6px", width: "100%", maxWidth: 260, border: `1px solid ${C.inputBorder}`, borderRadius: 7, background: "#fff", transition: "border-color .12s" }}
        onFocus={(e) => { e.target.style.borderColor = C.ink; }} />
    );
  }

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, minWidth: 0 }}>
      <span style={{ fontFamily: mono, fontSize: 13, fontWeight: 600, color: C.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{customName || name}</span>
      {!disabled && (
        <button onClick={startEdit} title="Rename"
          style={{ all: "unset", cursor: "pointer", fontSize: 12, color: C.t3, padding: "0 2px", lineHeight: 1, flexShrink: 0 }}>&#9998;</button>
      )}
    </span>
  );
}

// ---- Owner chip with bulk popover ----

function PopoverItem({ label, onClick }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick}
      style={{ all: "unset", cursor: "pointer", padding: "5px 10px", fontSize: 12, fontWeight: 500, color: C.ink, borderRadius: 5, background: h ? C.rowHover : "transparent" }}>{label}</button>
  );
}

function OwnerChip({ owner, disabled, onBulk }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <span ref={ref} style={{ position: "relative", display: "inline-flex" }}>
      <button onClick={() => setOpen(!open)} disabled={disabled}
        aria-haspopup="true" aria-expanded={open}
        style={{ all: "unset", cursor: disabled ? "default" : "pointer" }}>
        <Chip tone="none">{owner}</Chip>
      </button>
      {open && (
        <div style={{ position: "absolute", top: "100%", right: 0, marginTop: 4, background: "#fff", border: `1px solid ${C.border}`, borderRadius: 7, boxShadow: "0 6px 18px -8px rgba(28,27,25,.25)", padding: 6, zIndex: 10, display: "flex", flexDirection: "column", gap: 2, minWidth: 90 }}>
          <PopoverItem label="All on" onClick={() => { onBulk(owner, "on"); setOpen(false); }} />
          <PopoverItem label="All off" onClick={() => { onBulk(owner, "off"); setOpen(false); }} />
        </div>
      )}
    </span>
  );
}

// ---- Reload banner ----

function ReloadBanner({ mode, onDismiss }) {
  const [reloading, setReloading] = useState(false);
  const [reloadResult, setReloadResult] = useState(null);
  const [reloadError, setReloadError] = useState(null);

  if (!mode) return null;

  const doReload = async () => {
    setReloading(true);
    setReloadResult(null);
    setReloadError(null);
    try {
      const r = await postJSON("/api/reload", {});
      setReloadResult(r);
    } catch (e) {
      setReloadError(e.message);
    } finally {
      setReloading(false);
    }
  };

  return (
    <div style={{ position: "sticky", top: 0, zIndex: 5, marginBottom: 16, background: C.amberBg, border: `1px solid ${C.amberBorder}`, borderRadius: 8, padding: "12px 14px", fontSize: 13, lineHeight: 1.6, color: C.amber }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <div style={{ flex: 1 }}>
          {mode === "reload" && !reloadResult && (
            <>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Changes pending</div>
              <div style={{ marginBottom: 6 }}>
                <strong>1.</strong> Reload the server to apply the new controls.
              </div>
              <GhostBtn onClick={doReload} style={{ marginBottom: 6 }}>
                {reloading ? "Reloading..." : "Reload server"}
              </GhostBtn>
              {reloadError && <div style={{ color: C.danger, fontSize: 12 }}>{reloadError}</div>}
              <div><strong>2.</strong> Then reconnect in Claude Code: run <code style={{ fontFamily: mono, fontSize: 12, background: C.subtle, padding: "1px 5px", borderRadius: 4 }}>/mcp</code> and reconnect the server.</div>
            </>
          )}
          {mode === "reload" && reloadResult && (
            <>
              <div style={{ fontWeight: 600, marginBottom: 4, color: C.ok }}>Server reloaded</div>
              <div style={{ fontSize: 12, color: C.t2, marginBottom: 4 }}>
                v{reloadResult.version}, {reloadResult.project_commands} project commands, {reloadResult.framework_prompts} framework prompts
              </div>
              <div>Now reconnect in Claude Code: run <code style={{ fontFamily: mono, fontSize: 12, background: C.subtle, padding: "1px 5px", borderRadius: 4 }}>/mcp</code> and reconnect the server.</div>
            </>
          )}
          {mode === "reconnect" && (
            <>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Reconnect needed</div>
              <div>Reconnect in Claude Code: run <code style={{ fontFamily: mono, fontSize: 12, background: C.subtle, padding: "1px 5px", borderRadius: 4 }}>/mcp</code> and reconnect the server.</div>
            </>
          )}
        </div>
        <button onClick={onDismiss} title="Dismiss"
          style={{ all: "unset", cursor: "pointer", fontSize: 16, color: C.t3, padding: "0 2px", lineHeight: 1 }}>x</button>
      </div>
    </div>
  );
}

// ---- Command row ----

function CommandRowItem({ cmd, disabled, busy, note, onToggle, onRename, onBulk }) {
  const dim = !cmd.effective;
  const inv = commandInvocation(cmd.name);
  return (
    <div style={{ borderTop: `1px solid ${C.borderRow}`, padding: "8px 0 4px", opacity: dim ? 0.55 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, minHeight: 26, flexWrap: "wrap" }}>
        <TerminalGlyph />
        <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 6 }}>
          <NameEditor name={cmd.default_name || cmd.name} customName={cmd.custom ? cmd.name : null} rowKey={cmd.key} disabled={disabled || busy} onSave={onRename} />
          {cmd.custom && <Chip tone="stat" style={{ fontSize: 9 }}>renamed</Chip>}
        </div>
        <OwnerChip owner={cmd.owner} disabled={disabled || busy} onBulk={onBulk} />
        {cmd.template && <span title="One toggle controls the template; every generated entry follows it."><Chip>template</Chip></span>}
        <span style={{ fontFamily: mono, fontSize: 10.5, color: C.t3, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={inv}>{inv}</span>
        <CopyPrompt icon text={inv} title={"Copy " + inv} toast="Copied, paste it into your agent" />
        <Switch on={cmd.effective} disabled={disabled || busy} onClick={() => onToggle(cmd.key, cmd.effective ? "off" : "on")}
          title={cmd.effective ? "Turn off" : "Turn on"} />
      </div>
      {(cmd.description || cmd.path) && (
        <div style={{ paddingLeft: 34, paddingTop: 2, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {cmd.description && <span style={{ fontSize: 12, color: C.tMuted, lineHeight: 1.5 }}>{cmd.description}</span>}
          <span style={{ fontFamily: mono, fontSize: 10.5, color: C.t3 }}>{cmd.path}</span>
        </div>
      )}
      <div style={{ paddingLeft: 34 }}><RowNote note={note} /></div>
    </div>
  );
}

// ---- Resource row ----

function ResourceRowItem({ res, disabled, busy, note, onToggle, onRename }) {
  const ref = fileRef(res.key + "/index.md");
  return (
    <div style={{ borderTop: `1px solid ${C.borderRow}`, padding: "8px 0 4px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, minHeight: 26, flexWrap: "wrap" }}>
        <FileGlyph w={18} />
        <div style={{ flex: 1, minWidth: 0, display: "flex", alignItems: "center", gap: 6 }}>
          <NameEditor name={res.default_name} customName={res.custom ? res.name : null} rowKey={res.key} disabled={disabled || busy} onSave={onRename} />
          {res.custom && <Chip tone="stat" style={{ fontSize: 9 }}>renamed</Chip>}
        </div>
        <Chip tone="none">{res.kind}</Chip>
        <span style={{ fontFamily: mono, fontSize: 10.5, color: C.t3, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={ref}>{ref}</span>
        <CopyPrompt icon text={ref} title={"Copy " + ref} toast="Copied, paste it into your agent" />
        <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5, color: C.tMuted, whiteSpace: "nowrap" }}>
          listed in picker
          <Switch on={res.effective} disabled={disabled || busy} onClick={() => onToggle(res.key, res.effective ? "off" : "on")}
            title={res.effective ? "Hide from picker" : "List in picker"} />
        </label>
      </div>
      {res.description && (
        <div style={{ paddingLeft: 26, paddingTop: 2 }}>
          <span style={{ fontSize: 12, color: C.tMuted, lineHeight: 1.5 }}>{res.description}</span>
        </div>
      )}
      <div style={{ paddingLeft: 26 }}><RowNote note={note} /></div>
    </div>
  );
}

// ---- Structural row (always listed by the server, no toggle) ----

function StructuralRow({ row }) {
  const ref = row.path ? fileRef(row.path) : null;
  return (
    <div style={{ borderTop: `1px solid ${C.borderRow}`, padding: "8px 0 4px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, minHeight: 26, flexWrap: "wrap" }}>
        <FileGlyph w={18} />
        <span style={{ fontFamily: mono, fontSize: 12.5, fontWeight: 600, color: C.t2, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.name}</span>
        <Chip tone="none">built-in</Chip>
        {ref && (
          <>
            <span style={{ fontFamily: mono, fontSize: 10.5, color: C.t3, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={ref}>{ref}</span>
            <CopyPrompt icon text={ref} title={"Copy " + ref} toast="Copied, paste it into your agent" />
          </>
        )}
        <span style={{ fontSize: 11.5, color: C.t3, whiteSpace: "nowrap" }}>always listed</span>
      </div>
      {row.description && (
        <div style={{ paddingLeft: 26, paddingTop: 2 }}>
          <span style={{ fontSize: 12, color: C.tMuted, lineHeight: 1.5 }}>{row.description}</span>
        </div>
      )}
    </div>
  );
}

// ---- Pinned row ----

function PinRow({ path, disabled, busy, note, onRemove }) {
  const [h, hp] = useHover();
  const ref = fileRef(path);
  return (
    <div style={{ borderTop: `1px solid ${C.borderRow}`, padding: "6px 0 3px" }}>
      <div {...hp} style={{ display: "flex", alignItems: "center", gap: 8, minHeight: 24 }}>
        <FileGlyph w={18} />
        <span style={{ fontFamily: mono, fontSize: 12, color: C.t2, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={path}>{path}</span>
        <Chip tone="none">pinned</Chip>
        <CopyPrompt icon text={ref} title={"Copy " + ref} toast="Copied, paste it into your agent" />
        <button onClick={onRemove} disabled={disabled || busy} title={"Unpin " + path}
          style={{ all: "unset", cursor: disabled || busy ? "default" : "pointer", fontSize: 11.5, fontWeight: 600, color: h ? C.danger : C.t3, padding: "1px 6px" }}>
          unpin
        </button>
      </div>
      <div style={{ paddingLeft: 26 }}><RowNote note={note} /></div>
    </div>
  );
}

// ---- Main component ----

export default function Controls() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [busyKey, setBusyKey] = useState(null);
  const [notes, setNotes] = useState({});
  const [bannerMode, setBannerMode] = useState(null); // "reload" | "reconnect" | null

  const load = () => {
    getJSON("/api/controls").then((d) => { setData(d); setErr(null); }).catch((e) => setErr(e.message));
  };
  useEffect(load, []);

  // Determine if a POST is a command toggle/bulk (needs reload) or a command rename (needs reconnect only).
  const needsBanner = (body) => {
    if (body.section === "commands") return "reload";
    if (body.bulk) return "reload";
    if (body.name && body.name.key) {
      // Check if the key is a command key (not starting with modules/ connections/ agents/ for resource)
      // Command renames need reconnect only
      const isResource = data?.resources?.some((r) => r.key === body.name.key);
      if (!isResource) return "reconnect";
    }
    // Resource toggles, resource renames, pins: no banner (live)
    return null;
  };

  const post = (rowKey, body) => {
    setBusyKey(rowKey);
    postJSON("/api/controls", body)
      .then((d) => {
        const { note, ...rest } = d;
        setData(rest);
        setErr(null);
        setNotes((n) => ({ ...n, [rowKey]: note ? { msg: note } : null }));
        // Show banner if needed
        const bannerNeeded = needsBanner(body);
        if (bannerNeeded) {
          setBannerMode((prev) => {
            // "reload" wins if both pend
            if (prev === "reload" || bannerNeeded === "reload") return "reload";
            return bannerNeeded;
          });
        }
      })
      .catch((e) => {
        setNotes((n) => ({ ...n, [rowKey]: { msg: e.message, error: true } }));
        load();
      })
      .finally(() => setBusyKey(null));
  };

  const setCommand = (key, value) => post(key, { section: "commands", key, value });
  const setResource = (key, value) => post(key, { section: "resources", key, value });
  const renameCommand = (key, value) => post(key, { name: { key, value } });
  const renameResource = (key, value) => post(key, { name: { key, value } });
  const bulkToggle = (owner, value) => post("bulk:" + owner, { bulk: { owner, value } });
  const unpin = (path) => post("pin:" + path, { pin: path, pinned: false });

  if (err && !data) return <div style={{ color: C.danger, fontSize: 13.5, padding: 20 }}>Could not load: {err}</div>;
  if (!data && !err) return <div style={{ padding: "60px 0", textAlign: "center", color: C.t3, fontSize: 14 }}>Loading...</div>;

  const disabled = !!err; // malformed controls.yaml (409) disables every toggle

  return (
    <div>
      <h1 style={{ ...pageTitle, marginBottom: 5 }}>Controls</h1>
      <p style={{ margin: "0 0 20px", color: C.tMuted, fontSize: 13.5, lineHeight: 1.55, maxWidth: 640 }}>
        What the server exposes, from <span style={{ fontFamily: mono }}>controls.yaml</span>. Each change writes one line in the file. Hand edits keep working. Resource changes are live. Command toggles apply after <span style={{ fontFamily: mono }}>gcontext reload</span> plus an <span style={{ fontFamily: mono }}>/mcp</span> reconnect. Renames apply after the reconnect alone.
      </p>

      {err && (
        <div style={{ marginBottom: 18, background: C.missFill, border: `1px solid ${C.missBorder}`, color: C.missText, borderRadius: 7, padding: "11px 13px", fontSize: 13, lineHeight: 1.5 }}>
          {err}. Toggles and editors are disabled until the file parses. Fix controls.yaml by hand and refresh.
        </div>
      )}

      <ReloadBanner mode={bannerMode} onDismiss={() => setBannerMode(null)} />

      {data && (
        <>
          {/* Commands section */}
          <div style={{ ...sectionLabel, marginBottom: 11 }}>Commands ({(data.commands || []).length})</div>
          <div style={{ ...cardBase, padding: "4px 16px 8px", marginBottom: 22 }}>
            {(data.commands || []).length === 0 ? (
              <EmptyState style={{ margin: "8px 0" }}>No commands registered.</EmptyState>
            ) : (
              (data.commands || []).map((cmd) => (
                <CommandRowItem key={cmd.key} cmd={cmd} disabled={disabled} busy={busyKey === cmd.key}
                  note={notes[cmd.key]} onToggle={setCommand} onRename={renameCommand} onBulk={bulkToggle} />
              ))
            )}
          </div>

          {/* Resources section */}
          <div style={{ ...sectionLabel, marginBottom: 11 }}>Resources</div>
          <div style={{ ...cardBase, padding: "4px 16px 8px", marginBottom: 22 }}>
            {(data.structural || []).length === 0 && (data.resources || []).length === 0 && (data.pinned || []).length === 0 ? (
              <EmptyState style={{ margin: "8px 0" }}>No resources or pinned files.</EmptyState>
            ) : (
              <>
                {(data.structural || []).map((row) => (
                  <StructuralRow key={"structural:" + row.key} row={row} />
                ))}
                {(data.resources || []).map((res) => (
                  <ResourceRowItem key={res.key} res={res} disabled={disabled} busy={busyKey === res.key}
                    note={notes[res.key]} onToggle={setResource} onRename={renameResource} />
                ))}
                {(data.pinned || []).length > 0 && (
                  <>
                    {(data.resources || []).length > 0 && (
                      <div style={{ ...sectionLabel, margin: "10px 0 4px", fontSize: 10 }}>Pinned files</div>
                    )}
                    {data.pinned.map((p) => (
                      <PinRow key={p} path={p} disabled={disabled} busy={busyKey === "pin:" + p}
                        note={notes["pin:" + p]} onRemove={() => unpin(p)} />
                    ))}
                  </>
                )}
              </>
            )}
          </div>

          {/* Stale entries */}
          {(data.stale || []).length > 0 && (
            <p style={{ margin: "0 0 14px", fontSize: 12, color: C.t3, lineHeight: 1.6 }}>
              Entries with no matching file on disk (kept in controls.yaml, delete the lines by hand if stale):{" "}
              {data.stale.map((s) => s.key).join(", ")}
            </p>
          )}
        </>
      )}
    </div>
  );
}
