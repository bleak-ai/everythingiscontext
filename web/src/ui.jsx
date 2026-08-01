import React, { createContext, useContext, useEffect, useRef, useState } from "react";

// Warm-paper / monospace-accent design tokens (see design handoff README).
export const C = {
  // surfaces
  bg: "#efece8", panel: "#fff", subtle: "#faf8f3", sidebar: "#f6f3ec",
  soft: "#efe9dd", rowHover: "#f7f3ec",
  // ink + text
  ink: "#1f1d1a", inkHover: "#000",
  tFolder: "#33312c", t2: "#4A4842", tMuted: "rgba(0,0,0,.55)", t3: "rgba(0,0,0,.45)", tLabel: "rgba(0,0,0,.4)",
  faint: "#c7c0af", disabled: "#cdc6b8",
  // borders
  border: "#e6e1d6", borderStrong: "#d9d4c8", borderInner: "#eee7da", borderRow: "#f1ece1", inputBorder: "#ddd7cb",
  divider: "#e4ded2",
  // terracotta accent (primary "copy a prompt" action)
  accent: "#c2603a", accentHover: "#ad5230", accentBg: "#fff6ef", accentBg2: "#fffaf4", accentBorder: "#e0b89f", accentSoft: "#f7f1ea",
  accentBgHover: "#fbeadf", accentBorderStrong: "#d99a7a",
  // success / present / connected
  ok: "#3d6b4a", okBg: "#eef5ef", okBorder: "#9cbfa6",
  // error / missing
  danger: "#a8492a", dangerHover: "#8f3a20", dangerFill: "#fbf2ee", dangerBorder: "#d3a896",
  missFill: "#fbf2ee", missBorder: "#d3a896", missText: "#a8492a",
  // status (in progress / needs reply)
  amber: "#8a6d2e", amberBg: "#f6efdf", amberBorder: "#c9b48a",
  // code block
  onDark: "#e7dfd1", codeBg: "#2c2825", codeText: "#e7dfd1",
  // markdown presentation (peek panel)
  factBg: "#fdfcf9", calloutDangerBorder: "#ecd3c6", stepNextBorder: "#ecd0bc",
  codeDim: "rgba(231,223,209,.5)", codeRule: "rgba(231,223,209,.12)",
  // folder glyph
  glyph: "#c7c0af",
};
export const mono = "'IBM Plex Mono', ui-monospace, Menlo, monospace";

// Canonical card + section styling. Workspace is the reference; every card grid
// points at these so radius/hover/label never drift per-view.
export const sectionLabel = { fontFamily: mono, fontSize: 11, fontWeight: 600, letterSpacing: ".09em", textTransform: "uppercase", color: C.tLabel };
// The one page-title style. Callers add their own margin.
export const pageTitle = { margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: "-.02em", color: C.ink };
export const cardBase = { borderRadius: 10, border: `1px solid ${C.border}`, background: "#fff", transition: "all .12s" };
// Full `border` shorthand, NOT the borderColor longhand: React's style diffing mishandles
// a longhand overriding a shorthand — on unhover it drops borderColor without re-expanding
// cardBase's border, leaving a colorless (= currentColor, ink) 1px border on the card.
export const cardHover = { border: `1px solid ${C.borderStrong}`, boxShadow: "0 6px 18px -14px rgba(28,27,25,.4)" };
export const cardGrid = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(232px, 1fr))", gap: 13 };

// Underline tab bar shared by the instance modal and Setup
// (Connection/Secrets) destinations. tabs: [{ key, label }].
export function Tabs({ tabs, active, onChange, style }) {
  return (
    <div style={{ display: "flex", gap: 26, borderBottom: `1px solid ${C.border}`, marginBottom: 22, ...style }}>
      {tabs.map((t) => {
        const on = t.key === active;
        return (
          <button key={t.key} onClick={() => onChange(t.key)}
            style={{ all: "unset", cursor: "pointer", display: "inline-flex", alignItems: "center", padding: "0 1px 10px", marginBottom: -1, fontSize: 14, fontWeight: 600, color: on ? C.ink : C.t3, borderBottom: `2px solid ${on ? C.accent : "transparent"}` }}>
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

// Phone-width check for the inline-style layout (no CSS classes to media-query).
const MQ = "(max-width: 760px)";
export function useIsMobile() {
  const [m, setM] = useState(() => window.matchMedia(MQ).matches);
  useEffect(() => {
    const mq = window.matchMedia(MQ);
    const fn = (e) => setM(e.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);
  return m;
}

// Inline :hover for elements that can't use a CSS class cleanly.
export function useHover() {
  const [h, setH] = useState(false);
  return [h, { onMouseEnter: () => setH(true), onMouseLeave: () => setH(false) }];
}

// Expand a `border: "1px solid X"` shorthand into longhands. React's style diffing
// mishandles a longhand (hover's borderColor) overriding a shorthand (base's border):
// on unhover it drops borderColor without re-expanding the shorthand, leaving a
// colorless (= currentColor, ink) border. All-longhand styles diff cleanly.
function expandBorder(s) {
  if (!s || !s.border) return s;
  const m = String(s.border).match(/^(\S+)\s+(\S+)\s+(.+)$/);
  if (!m) return s; // e.g. border: "none" — leave as-is
  const { border, ...rest } = s;
  return { borderWidth: m[1], borderStyle: m[2], borderColor: m[3], ...rest };
}

// Button with base/hover style objects merged (hover suppressed while disabled).
export function HBtn({ base = {}, hover = {}, disabled, style, ...props }) {
  const [h, hp] = useHover();
  return (
    <button
      {...hp}
      disabled={disabled}
      style={{ ...expandBorder(base), ...(h && !disabled ? expandBorder(hover) : null), ...expandBorder(style) }}
      {...props}
    />
  );
}

// Quiet secondary action (Refresh, Clear feed, Overview). `danger` tints it red.
export function GhostBtn({ children, onClick, danger, style }) {
  return (
    <HBtn
      base={{ height: 31, padding: "0 13px", borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: "pointer", transition: "all .15s", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 7, border: `1px solid ${danger ? C.dangerBorder : C.border}`, background: danger ? C.dangerFill : C.subtle, color: danger ? C.danger : C.tMuted, ...style }}
      hover={{ background: danger ? C.missFill : C.soft, borderColor: danger ? C.danger : C.borderStrong, color: danger ? C.dangerHover : C.ink }}
      onClick={onClick}
    >{children}</HBtn>
  );
}

// The standard "← Back" button. Callers add margins via style.
export function BackBtn({ onClick, style }) {
  const [h, hp] = useHover();
  return (
    <button {...hp} onClick={onClick} title="Back"
      style={{ display: "inline-flex", alignItems: "center", gap: 6, flexShrink: 0, padding: "6px 11px", border: `1px solid ${h ? C.borderStrong : C.border}`, background: h ? C.soft : C.subtle, borderRadius: 7, fontSize: 13, fontWeight: 500, color: h ? C.ink : C.tMuted, cursor: "pointer", transition: "all .12s", ...style }}>← Back</button>
  );
}

// Input whose border goes ink on focus.
export function Field({ style = {}, onFocus, onBlur, ...props }) {
  const [f, setF] = useState(false);
  return (
    <input
      {...props}
      onFocus={(e) => { setF(true); onFocus?.(e); }}
      onBlur={(e) => { setF(false); onBlur?.(e); }}
      style={{ outline: "none", border: `1px solid ${f ? C.ink : C.inputBorder}`, borderRadius: 7, background: "#fff", transition: "border-color .12s", ...style }}
    />
  );
}

// Small monospace status pill. tone: rend (green) | miss (red) | stat (amber) | none (neutral).
const CHIP = {
  rend: { color: C.ok, background: C.okBg, border: C.okBorder },
  ok: { color: C.ok, background: C.okBg, border: C.okBorder },
  miss: { color: C.danger, background: C.missFill, border: C.missBorder },
  stat: { color: C.amber, background: C.amberBg, border: C.amberBorder },
  none: { color: C.t3, background: C.subtle, border: C.inputBorder },
};
export function Chip({ tone = "none", children, style }) {
  const s = CHIP[tone] || CHIP.none;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontFamily: mono, fontSize: 9.5, fontWeight: 600, padding: "2px 7px", borderRadius: 20, color: s.color, background: s.background, border: `1px solid ${s.border}`, whiteSpace: "nowrap", ...style }}>{children}</span>
  );
}

// The one empty-state treatment: dashed border, subtle bg, centered muted text.
export function EmptyState({ children, style }) {
  return (
    <div style={{ padding: "40px 28px", textAlign: "center", border: `1px dashed ${C.borderStrong}`, borderRadius: 12, background: C.subtle, color: C.t3, fontSize: 13.5, lineHeight: 1.6, ...style }}>{children}</div>
  );
}

// The beige folder glyph (CSS shape, no asset). Scales with `w`.
export function FolderGlyph({ w = 30 }) {
  const h = Math.round(w * 0.77);
  return (
    <div style={{ position: "relative", width: w, height: h, flexShrink: 0, marginTop: 1 }}>
      <div style={{ position: "absolute", top: -Math.round(h * 0.22), left: 0, width: Math.round(w * 0.43), height: Math.round(h * 0.26), background: C.glyph, borderRadius: "3px 3px 0 0" }} />
      <div style={{ position: "absolute", inset: 0, top: 0, background: C.glyph, borderRadius: 3 }} />
    </div>
  );
}

// Document glyph: a page with a folded top-right corner + a few text lines.
export function FileGlyph({ w = 24 }) {
  const h = Math.round(w * 1.24);
  return (
    <svg width={w} height={h} viewBox="0 0 24 30" fill="none" style={{ flexShrink: 0 }}>
      <path d="M4 2h11l6 6v18a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"
        fill="#fff" stroke={C.glyph} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M15 2v6h6" stroke={C.glyph} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M6 15h9M6 19h9M6 23h6" stroke={C.glyph} strokeWidth="1.4" strokeLinecap="round" opacity="0.55" />
    </svg>
  );
}

// --- Confirm modal + toast, exposed via useUi() ------------------------------
const UiCtx = createContext(null);
export function useUi() { return useContext(UiCtx); }

function ConfirmModal({ title, message, action, onConfirm, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(28,27,25,.32)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, zIndex: 50 }}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: "100%", maxWidth: 400, background: "#fff", borderRadius: 11, padding: 24, boxShadow: "0 24px 60px -20px rgba(28,27,25,.4)" }}>
        <h3 style={{ margin: "0 0 8px", fontSize: 17, fontWeight: 600, letterSpacing: "-.01em" }}>{title}</h3>
        <p style={{ margin: "0 0 22px", color: C.tMuted, fontSize: 14, lineHeight: 1.55 }}>{message}</p>
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <HBtn base={{ height: 40, padding: "0 16px", border: `1px solid ${C.borderStrong}`, background: "#fff", color: C.tMuted, borderRadius: 7, fontSize: 14, fontWeight: 500, cursor: "pointer" }} hover={{ color: C.ink, borderColor: "#c7c2b9" }} onClick={onClose}>Cancel</HBtn>
          <HBtn base={{ height: 40, padding: "0 18px", border: "none", background: C.danger, color: "#fff", borderRadius: 7, fontSize: 14, fontWeight: 600, cursor: "pointer", transition: "background .12s" }} hover={{ background: C.dangerHover }} onClick={() => { onConfirm(); onClose(); }}>{action}</HBtn>
        </div>
      </div>
    </div>
  );
}

function Toast({ msg, error }) {
  return (
    <div style={{ position: "fixed", bottom: 84, left: "50%", transform: "translateX(-50%)", background: error ? C.danger : C.ink, color: "#fff", padding: "11px 18px", borderRadius: 8, fontSize: 13.5, fontWeight: 500, boxShadow: "0 12px 30px -10px rgba(28,27,25,.5)", zIndex: 60, display: "flex", alignItems: "center", gap: 9 }}>
      <span style={{ fontWeight: 700 }}>{error ? "⚠" : "✓"}</span>{msg}
    </div>
  );
}

export function UiProvider({ children }) {
  const [confirm, setConfirm] = useState(null);
  const [toast, setToast] = useState(null);
  const tRef = useRef();
  const show = (msg, ms, error) => {
    clearTimeout(tRef.current);
    setToast({ msg, error });
    tRef.current = setTimeout(() => setToast(null), ms);
  };
  const api = {
    confirm: (opts) => setConfirm(opts),
    toast: (msg, ms = 1900) => show(msg, ms, false),
    error: (msg, ms = 3500) => show(msg, ms, true),
  };
  return (
    <UiCtx.Provider value={api}>
      {children}
      {confirm && <ConfirmModal {...confirm} onClose={() => setConfirm(null)} />}
      {toast && <Toast msg={toast.msg} error={toast.error} />}
    </UiCtx.Provider>
  );
}
