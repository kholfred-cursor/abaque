/**
 * Design tokens: the single source of truth. tokens.css mirrors these values as CSS
 * custom properties (a test checks that both stay identical).
 */
export const tokens = {
  color: {
    paper: "#f7f9fb",
    surface: "#ffffff",
    ink: "#1f2a33",
    muted: "#566573",
    line: "#d3dae1",
    action: "#1a5fb4",
    actionInk: "#ffffff",
    danger: "#a8231c",
    dangerSurface: "#fdecea",
    notice: "#7a5a00",
    noticeSurface: "#fff6d6",
    success: "#1e6b2e",
    successSurface: "#e6f4ea",
    focus: "#1a5fb4",
  },
  font: {
    family: '"Atkinson Hyperlegible Next Variable", system-ui, sans-serif',
    sizeSmall: "0.875rem",
    sizeBody: "1rem",
    sizeLead: "1.25rem",
    sizeTitle: "1.75rem",
    lineHeight: "1.5",
  },
  space: {
    xs: "0.25rem",
    sm: "0.5rem",
    md: "1rem",
    lg: "1.5rem",
    xl: "2.5rem",
  },
  radius: {
    control: "6px",
    panel: "10px",
  },
  size: {
    touch: "44px",
    content: "60rem",
    form: "26rem",
  },
} as const;

type Nested = { readonly [key: string]: string | Nested };

/** "color.actionInk" -> "--color-action-ink" */
export function cssVariableName(path: string): string {
  return `--${path.replace(/\./g, "-").replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}`;
}

export function flattenTokens(node: Nested = tokens, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(node)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") {
      out[cssVariableName(path)] = value;
    } else {
      Object.assign(out, flattenTokens(value, path));
    }
  }
  return out;
}
