import React, { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { getJSON } from "./lib.js";
import { C, mono, label } from "./ui.jsx";

// Files = read-only browser over the project folder. Left: the tree from
// /api/tree (secrets.env and machine folders are excluded server-side).
// Right: the selected file, markdown rendered, everything else plain text.

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

function TreeRow({ node, depth, selected, open, onToggle, onSelect }) {
  const isSel = selected === node.path;
  return (
    <>
      <button
        onClick={() => (node.dir ? onToggle(node.path) : onSelect(node.path))}
        title={node.path}
        style={{ all: "unset", cursor: "pointer", display: "block", width: "100%", boxSizing: "border-box", padding: "2px 0", paddingLeft: depth * 14, fontFamily: mono, fontSize: 12, lineHeight: 1.7, color: node.dir ? C.ink : isSel ? C.accent : C.t2, fontWeight: node.dir || isSel ? 600 : 400, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {node.dir ? (open.has(node.path) ? "▾ " : "▸ ") : "  "}{node.name}{node.dir ? "/" : ""}
      </button>
      {node.dir && open.has(node.path) && node.children.map((c) => (
        <TreeRow key={c.path} node={c} depth={depth + 1} selected={selected} open={open} onToggle={onToggle} onSelect={onSelect} />
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

  if (!path) return <p style={{ fontFamily: mono, fontSize: 11.5, color: C.t3, margin: 0 }}>pick a file on the left</p>;
  if (err) return <p style={{ fontFamily: mono, fontSize: 12, color: C.danger, margin: 0 }}>{path}: {err}</p>;
  if (!file) return <p style={{ fontFamily: mono, fontSize: 11.5, color: C.t3, margin: 0 }}>loading…</p>;

  return (
    <div>
      <div style={{ fontFamily: mono, fontSize: 11.5, color: C.t3, marginBottom: 12, borderBottom: `1px solid ${C.borderInner}`, paddingBottom: 8 }}>
        {file.path} · {file.size} B
      </div>
      {path.endsWith(".md") ? (
        <div className="gc-md">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>{file.content}</ReactMarkdown>
        </div>
      ) : (
        <pre className="gc-scroll" style={{ margin: 0, fontFamily: mono, fontSize: 12, lineHeight: 1.7, whiteSpace: "pre-wrap", overflow: "auto" }}>{file.content}</pre>
      )}
    </div>
  );
}

export default function Files() {
  const [entries, setEntries] = useState(null);
  const [err, setErr] = useState(null);
  const [selected, setSelected] = useState(null);
  const [open, setOpen] = useState(() => new Set(["connections", "modules"]));

  useEffect(() => { getJSON("/api/tree").then((d) => setEntries(d.tree)).catch((e) => setErr(e.message)); }, []);
  const roots = useMemo(() => buildTree(entries || []), [entries]);
  const toggle = (path) => setOpen((prev) => {
    const next = new Set(prev);
    next.has(path) ? next.delete(path) : next.add(path);
    return next;
  });

  if (err) return <p style={{ fontFamily: mono, fontSize: 12, color: C.danger }}>{err}</p>;
  if (!entries) return <p style={{ fontFamily: mono, fontSize: 11.5, color: C.t3 }}>loading…</p>;

  return (
    <div style={{ display: "flex", gap: 32, alignItems: "flex-start", flexWrap: "wrap" }}>
      <div className="gc-scroll" style={{ flex: "0 1 220px", minWidth: 180, maxHeight: "75vh", overflowY: "auto" }}>
        <div style={{ ...label, marginBottom: 8 }}>project</div>
        {roots.map((n) => (
          <TreeRow key={n.path} node={n} depth={0} selected={selected} open={open} onToggle={toggle} onSelect={setSelected} />
        ))}
      </div>
      <div style={{ flex: "1 1 420px", minWidth: 300 }}>
        <Viewer path={selected} />
      </div>
    </div>
  );
}
