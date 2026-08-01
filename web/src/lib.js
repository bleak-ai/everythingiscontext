// The whole data seam: every page reads the local server's /api/* routes.
// The dashboard is read-only; the agent (via MCP) is what changes the project.

export async function getJSON(path) {
  const r = await fetch(path);
  // Non-JSON bodies (proxy 502 etc.) must not surface as parse errors.
  const d = await r.json().catch(() => ({ error: `${r.status} ${r.statusText}` }));
  if (!r.ok || (d && d.error)) throw new Error((d && d.error) || `${r.status}`);
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

// Agent-ready prompts for a file or folder reference. The copied text names
// the gcontext MCP server, so any agent can locate the path without guessing
// which server or tool it belongs to.
export const filePrompt = (path) =>
  `From the gcontext MCP server, read "${path}" and use it as context for this task.`;
export const folderPrompt = (path) =>
  `From the gcontext MCP server, explore the folder "${path.replace(/\/$/, "")}/": check its files and read the relevant ones.`;
export const refPrompt = (path, isDir) => (isDir ? folderPrompt(path) : filePrompt(path));

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
