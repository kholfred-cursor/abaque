/**
 * The five-colour Régnier scale, in display order. Each colour always comes with a
 * symbol so meaning never relies on colour alone. Mirrored in docs/design/scale.json
 * (used by the PDF report in lot 4); keys match the backend COLOR_KEYS.
 */
export type ScaleKey = "++" | "+" | "~" | "-" | "--";

export interface ScaleColor {
  readonly key: ScaleKey;
  readonly hex: string;
  readonly textColor: string;
  readonly symbol: string;
  readonly weight: number;
  readonly labels: { readonly agreement: string; readonly score: string };
}

export const DARK_TEXT = "#1f2a33";
/** Black, not white: on #2e8b3c and #e83030 white only reaches ~4.3:1 (< 4.5 required). */
export const BLACK_TEXT = "#000000";

export const scale: readonly ScaleColor[] = [
  {
    key: "++",
    hex: "#2e8b3c",
    textColor: BLACK_TEXT,
    symbol: "++",
    weight: 2,
    labels: { agreement: "Tout à fait d'accord", score: "5 — Élevé" },
  },
  {
    key: "+",
    hex: "#7ecb4d",
    textColor: DARK_TEXT,
    symbol: "+",
    weight: 1,
    labels: { agreement: "Plutôt d'accord", score: "4 — Moyen" },
  },
  {
    key: "~",
    hex: "#f5d94e",
    textColor: DARK_TEXT,
    symbol: "~",
    weight: 0,
    labels: { agreement: "Avis partagé, opinion mitigée", score: "3 — Incertain / Mitigé" },
  },
  {
    key: "-",
    hex: "#f0a8b8",
    textColor: DARK_TEXT,
    symbol: "−",
    weight: -1,
    labels: { agreement: "Plutôt pas d'accord", score: "2 — Faible" },
  },
  {
    key: "--",
    hex: "#e83030",
    textColor: BLACK_TEXT,
    symbol: "−−",
    weight: -2,
    labels: { agreement: "Pas du tout d'accord", score: "1 — Très faible" },
  },
];

/** WCAG 2.x relative luminance and contrast ratio. */
function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function luminance(hex: string): number {
  const n = Number.parseInt(hex.slice(1), 16);
  return (
    0.2126 * channel((n >> 16) & 255) + 0.7152 * channel((n >> 8) & 255) + 0.0722 * channel(n & 255)
  );
}

export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}
