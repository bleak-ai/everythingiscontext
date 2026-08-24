import React from "react";
import { C, mono, useHover, useUi } from "./ui.jsx";
import { copyText } from "./lib.js";

// The one action surface in the app: copy a resource reference for the agent,
// fire a toast. The dashboard SEES the project; the agent (via MCP) USES it,
// so every action hands a gcontext://path reference to the clipboard.
//   full pill  -> <CopyPrompt text=… />           (⧉ Copy reference, terracotta)
//   icon only  -> <CopyPrompt text=… icon />      (26x26 ⧉, list rows)
export default function CopyPrompt({ text, label = "Copy reference", toast = "Copied, paste it into your agent", title, icon, style }) {
  const ui = useUi();
  const [h, hp] = useHover();
  const copy = (e) => {
    e?.stopPropagation?.();
    copyText(text);
    ui.toast(toast);
  };
  if (icon) {
    return (
      <button {...hp} onClick={copy} title={title || label}
        style={{ width: 26, height: 26, flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 13, lineHeight: 1, borderRadius: 7, border: `1px solid ${C.accentBorder}`, background: h ? C.accentBgHover : C.accentBg, color: C.accent, cursor: "pointer", transition: "all .12s", ...style }}>⧉</button>
    );
  }
  return (
    <button {...hp} onClick={copy} title={title}
      style={{ flexShrink: 0, display: "inline-flex", alignItems: "center", gap: 7, fontFamily: mono, fontSize: 12.5, fontWeight: 600, lineHeight: 1, padding: "9px 15px", borderRadius: 9, border: `1px solid ${h ? C.accent : C.accentBorderStrong}`, background: h ? C.accentBgHover : C.accentBg, color: C.accent, cursor: "pointer", transition: "all .12s", whiteSpace: "nowrap", ...style }}>
      <span style={{ fontSize: 13, lineHeight: 1 }}>⧉</span> {label}
    </button>
  );
}
