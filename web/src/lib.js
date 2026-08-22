// The whole data seam: every page reads the local server's /api/* routes.
// The dashboard is read-only; the agent (via MCP) is what changes the project.

export async function getJSON(path) {
  const r = await fetch(path);
  // Non-JSON bodies (proxy 502 etc.) must not surface as parse errors.
  const d = await r.json().catch(() => ({ error: `${r.status} ${r.statusText}` }));
  if (!r.ok || (d && d.error)) throw new Error((d && d.error) || `${r.status}`);
  return d;
}

// The one write seam: POST /api/controls (single controls.yaml entry per
// request). Throws with the server's message on 400/409 so callers can show
// it verbatim.
export async function postJSON(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const d = await r.json().catch(() => ({ error: `${r.status} ${r.statusText}` }));
  if (!r.ok) throw new Error((d && d.error) || `${r.status}`);
  return d;
}

export function copyText(text) {
  if (navigator.clipboard) return void navigator.clipboard.writeText(text);
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  ta.remove();
}

// Direct MCP resource references: @<server>:gcontext://<path>. Runtimes that
// support resource mentions (Claude Code et al.) resolve these mechanically;
// the server exposes every state file at gcontext://<path>. The server name
// is set once by App.jsx from /api/project.
let serverName = "gcontext";
export const setServerName = (name) => { if (name) serverName = name; };
export const fileRef = (path) => `@${serverName}:gcontext://${path}`;
export const folderRef = (path) => `@${serverName}:gcontext://${path.replace(/\/$/, "")}/`;
export const refPrompt = (path, isDir) => (isDir ? folderRef(path) : fileRef(path));
export const commandInvocation = (name) => `/mcp__${serverName}__${name}`;

// File-card label: "notes.md" -> "md", extensionless -> "file". Dotfiles (".env")
// stay "file" (lastIndexOf > 0), so the label never repeats the whole name.
export const fileLabel = (name) => { const i = (name || "").lastIndexOf("."); return i > 0 ? name.slice(i + 1).toLowerCase() : "file"; };

// "3h ago" / "2d ago": the one relative-time format for last-seen surfaces.
export const relSeen = (iso) => {
  const d = iso ? (Date.now() - new Date(iso).getTime()) / 86400000 : Infinity;
  if (!isFinite(d)) return "never";
  if (d < 1) { const h = Math.floor(d * 24); return h < 1 ? "just now" : `${h}h ago`; }
  return `${Math.max(1, Math.round(d))}d ago`;
};
