import { describe, expect, it } from "vitest";
import scaleJson from "../../../../docs/design/scale.json?raw";
import scaleCss from "./scale.module.css?raw";
import tokensCss from "./tokens.css?raw";
import { contrastRatio, scale } from "./scale";
import { SCALE_CLASS_NAMES } from "./scaleClass";
import { flattenTokens } from "./tokens";

describe("design tokens", () => {
  it("tokens.css mirrors tokens.ts exactly", () => {
    const fromCss = Object.fromEntries(
      [...tokensCss.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2]?.trim()]),
    );
    expect(fromCss).toEqual(flattenTokens());
  });
});

describe("five-colour scale", () => {
  it("matches docs/design/scale.json (used by the PDF report)", () => {
    const doc = JSON.parse(scaleJson) as {
      scale: { key: string; hex: string; symbol: string; weight: number; labels: object }[];
    };
    expect(doc.scale).toEqual(
      scale.map(({ key, hex, symbol, weight, labels }) => ({ key, hex, symbol, weight, labels })),
    );
  });

  it("gives every colour a text colour with at least 4.5:1 contrast", () => {
    for (const color of scale) {
      expect(contrastRatio(color.hex, color.textColor)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("never relies on colour alone: every colour has a distinct symbol", () => {
    expect(new Set(scale.map((c) => c.symbol)).size).toBe(scale.length);
  });

  it("scale.module.css carries the same colours as scale.ts", () => {
    for (const color of scale) {
      const block = new RegExp(`\\.${SCALE_CLASS_NAMES[color.key]} \\{([^}]*)\\}`).exec(
        scaleCss,
      )?.[1];
      expect(block).toContain(`background: ${color.hex}`);
      expect(block).toContain(`color: ${color.textColor}`);
    }
  });
});
