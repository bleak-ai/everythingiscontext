import React, { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { getJSON, postJSON, fileLabel, refPrompt } from "./lib.js";
import { C, mono, pageTitle, sectionLabel, EmptyState, useHover, useUi, FileGlyph } from "./ui.jsx";
import CopyPrompt from "./Copy.jsx";

// Files = read-only browser over the project folder. Left: the tree from
// /api/tree (secrets.env and machine folders are already excluded server-side).
// Right: the selected file, markdown rendered, everything else plain text.
// Every row and the reading pane can copy an agent-ready prompt pointing at
// the path inside the gcontext MCP server.

function buildTree(entries) {
  const roots = [];
  const byPath = {};
  for (const e of entries) {
    const node = { ...e, children: [] };
    byPath[e.path] = node;
    const slash = e.path.lastIndexOf("/");
    if (slash === -1) roots.push(node);
    else byPath[e.path.slice(0, slash)]?.children.push(node);
  }
  const sortNodes = (nodes) => {
    nodes.sort((a, b) => (b.dir - a.dir) || a.name.localeCompare(b.name));
    nodes.forEach((n) => sortNodes(n.children));
  };
  sortNodes(roots);
  return roots;
}

// Pushpin: filled accent when the file is pinned into the resource picker.
function PinIcon({ pinned, hover }) {
  const color = pinned ? C.accent : hover ? C.ink : C.t3;
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill={pinned ? color : "none"} style={{ display: "block" }}>
      <path d="M9 3h6l-1 7 3 3v2h-4l-1 6-1-6H7v-2l3-3-1-7z" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function PinBtn({ path, pinned, onPin, style }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={() => onPin(path, !pinned)}
      title={pinned ? `Unpin ${path} from the resource picker` : `Pin ${path} into the resource picker`}
      style={{ all: "unset", cursor: "pointer", width: 22, height: 22, display: "inline-flex", alignItems: "center", justifyContent: "center", borderRadius: 5, background: h ? C.soft : "transparent", flexShrink: 0, ...style }}>
      <PinIcon pinned={pinned} hover={h} />
    </button>
  );
}

function TreeRow({ node, depth, selected, open, onToggle, onSelect, pinnedSet, onPin }) {
  const [h, hp] = useHover();
  const isSel = selected === node.path;
  const ref = node.dir ? `${node.path}/` : node.path;
  const isPinned = pinnedSet.has(node.path);
  return (
    <>
      <div {...hp} style={{ display: "flex", alignItems: "center", gap: 6, borderRadius: 6, background: isSel ? "#fff" : h ? C.rowHover : "transparent", boxShadow: isSel ? "0 1px 2px rgba(28,27,25,.06)" : "none", transition: "background .1s", paddingRight: 6 }}>
        <button
          onClick={() => (node.dir ? onToggle(node.path) : onSelect(node.path))}
          title={node.path}
          style={{ all: "unset", cursor: "pointer", flex: 1, minWidth: 0, boxSizing: "border-box", padding: "5px 0 5px 8px", paddingLeft: 8 + depth * 14, display: "flex", alignItems: "center", gap: 7 }}>
          {node.dir
            ? <span style={{ fontSize: 9, color: C.t3, width: 10, flexShrink: 0 }}>{open.has(node.path) ? "▾" : "▸"}</span>
            : <span style={{ width: 10, flexShrink: 0 }} />}
          <span style={{ fontFamily: mono, fontSize: 12, fontWeight: node.dir ? 600 : 400, color: node.dir ? C.tFolder : C.t2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{node.name}{node.dir ? "/" : ""}</span>
        </button>
        {!node.dir && (h || isPinned) && <PinBtn path={node.path} pinned={isPinned} onPin={onPin} />}
        {h && <CopyPrompt icon text={refPrompt(ref, node.dir)} title={`Copy a reference to ${ref}`} style={{ width: 22, height: 22 }} />}
      </div>
      {node.dir && open.has(node.path) && node.children.map((c) => (
        <TreeRow key={c.path} node={c} depth={depth + 1} selected={selected} open={open} onToggle={onToggle} onSelect={onSelect} pinnedSet={pinnedSet} onPin={onPin} />
      ))}
    </>
  );
}

function Viewer({ path }) {
  const [file, setFile] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    if (!path) return;
    setFile(null); setErr(null);
    getJSON(`/api/file?path=${encodeURIComponent(path)}`).then(setFile).catch((e) => setErr(e.message));
  }, [path]);

  if (!path) {
    return (
      <EmptyState style={{ padding: "56px 28px" }}>
        <div style={{ fontFamily: mono, fontSize: 22, color: C.faint, marginBottom: 12 }}>◌</div>
        <div style={{ fontSize: 13.5 }}>Pick a file on the left to read it.</div>
      </EmptyState>
    );
  }
  if (err) return <div style={{ color: C.danger, fontSize: 13, padding: 18 }}>Couldn't read {path}: {err}</div>;
  if (!file) return <div style={{ padding: "40px 0", textAlign: "center", color: C.t3, fontSize: 13 }}>Loading…</div>;

  const isMd = path.endsWith(".md");
  return (
    <div style={{ border: `1px solid ${C.border}`, borderRadius: 11, background: "#fff", overflow: "hidden", animation: "gcpop .16s ease-out" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 16px", borderBottom: `1px solid ${C.borderInner}`, background: C.subtle }}>
        <FileGlyph w={16} />
        <span style={{ fontFamily: mono, fontSize: 12.5, fontWeight: 600, color: C.ink, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.path}</span>
        <span style={{ fontFamily: mono, fontSize: 10.5, color: C.t3, flexShrink: 0 }}>{fileLabel(path)} · {file.size} B</span>
        <CopyPrompt text={refPrompt(file.path, false)} title={`Copy a reference to ${file.path}`} style={{ padding: "6px 12px" }} />
      </div>
      <div style={{ padding: "18px 20px" }}>
        {isMd ? (
          <div className="gc-md">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{file.content}</ReactMarkdown>
          </div>
        ) : (
          <pre className="gc-scroll" style={{ margin: 0, fontFamily: mono, fontSize: 12, lineHeight: 1.7, color: C.ink, whiteSpace: "pre-wrap", overflow: "auto", maxHeight: "70vh" }}>{file.content}</pre>
        )}
      </div>
    </div>
  );
}

export default function Files() {
  const [entries, setEntries] = useState(null);
  const [err, setErr] = useState(null);
  const [selected, setSelected] = useState(null);
  const [open, setOpen] = useState(() => new Set(["connections", "modules"]));
  const [pinned, setPinned] = useState([]);
  const ui = useUi();

  useEffect(() => {
    getJSON("/api/tree").then((d) => setEntries(d.tree)).catch((e) => setErr(e.message));
    getJSON("/api/controls").then((d) => setPinned(d.pinned)).catch(() => {});
  }, []);
  const pinnedSet = useMemo(() => new Set(pinned), [pinned]);
  const onPin = (path, want) => {
    postJSON("/api/controls", { pin: path, pinned: want })
      .then((d) => { setPinned(d.pinned); ui.toast(want ? "Pinned into the resource picker" : "Unpinned"); })
      .catch((e) => ui.error(e.message));
  };
  const roots = useMemo(() => buildTree(entries || []), [entries]);
  const toggle = (path) => setOpen((prev) => {
    const next = new Set(prev);
    next.has(path) ? next.delete(path) : next.add(path);
    return next;
  });

  if (err) return <div style={{ color: C.danger, fontSize: 13.5, padding: 20 }}>Couldn't load: {err}</div>;
  if (!entries) return <div style={{ padding: "60px 0", textAlign: "center", color: C.t3, fontSize: 14 }}>Loading…</div>;

  return (
    <div>
      <h1 style={{ ...pageTitle, marginBottom: 5 }}>Files</h1>
      <p style={{ margin: "0 0 20px", color: C.tMuted, fontSize: 13.5, lineHeight: 1.55, maxWidth: 640 }}>
        The project folder as the agent sees it. Hover a row to copy a prompt that points your agent at that file or folder, or pin a file into the resource picker. <span style={{ fontFamily: mono }}>secrets.env</span> and machine folders never appear here.
      </p>
      <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div className="gc-scroll" style={{ flex: "0 1 280px", minWidth: 230, maxHeight: "72vh", overflowY: "auto", border: `1px solid ${C.border}`, borderRadius: 11, background: C.sidebar, padding: 8 }}>
          <div style={{ ...sectionLabel, padding: "4px 8px 8px" }}>Project</div>
          {roots.map((n) => (
            <TreeRow key={n.path} node={n} depth={0} selected={selected} open={open} onToggle={toggle} onSelect={setSelected} pinnedSet={pinnedSet} onPin={onPin} />
          ))}
        </div>
        <div style={{ flex: "1 1 460px", minWidth: 320 }}>
          <Viewer path={selected} />
        </div>
      </div>
    </div>
  );
}
