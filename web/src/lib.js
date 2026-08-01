// The whole data seam: every view reads the local server's /api/* routes.
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

// "3h ago" / "2d ago": the one relative-time format for last-seen surfaces.
export const relSeen = (iso) => {
  const d = iso ? (Date.now() - new Date(iso).getTime()) / 86400000 : Infinity;
  if (!isFinite(d)) return "never";
  if (d < 1) { const h = Math.floor(d * 24); return h < 1 ? "just now" : `${h}h ago`; }
  return `${Math.max(1, Math.round(d))}d ago`;
};
