// Minimal design tokens: warm paper background, ink text, IBM Plex.
// Everything else is plain elements styled inline where they are used.

import React, { useState } from "react";
import { copyText } from "./lib.js";

export const C = {
  bg: "#efece8",
  panel: "#fff",
  subtle: "#faf8f3",
  ink: "#1f1d1a",
  t2: "#4A4842",
  tMuted: "rgba(0,0,0,.55)",
  t3: "rgba(0,0,0,.45)",
  border: "#e6e1d6",
  borderInner: "#eee7da",
  accent: "#c2603a",
  ok: "#3d6b4a",
  danger: "#a8492a",
  amber: "#8a6d2e",
};

export const mono = "'IBM Plex Mono', ui-monospace, Menlo, monospace";

// Uppercase section label.
export const label = { fontFamily: mono, fontSize: 11, fontWeight: 600, letterSpacing: ".09em", textTransform: "uppercase", color: C.t3 };

// The one copy affordance: a small text link that flips to "copied".
// Used for connect commands, slash commands, and file/folder references.
export function CopyLink({ text, children, style }) {
  const [done, setDone] = useState(false);
  return (
    <button
      title={`copy ${text}`}
      onClick={(e) => { e.stopPropagation(); copyText(text); setDone(true); setTimeout(() => setDone(false), 1200); }}
      style={{ all: "unset", cursor: "pointer", fontFamily: mono, fontSize: 11, color: done ? C.ok : C.accent, flexShrink: 0, ...style }}>
      {done ? "copied" : children || "copy"}
    </button>
  );
}
