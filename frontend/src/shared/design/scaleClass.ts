import type { ScaleKey } from "./scale";
import styles from "./scale.module.css";

const CLASS_BY_KEY: Record<ScaleKey, string> = {
  "++": "veryHigh",
  "+": "high",
  "~": "mixed",
  "-": "low",
  "--": "veryLow",
};

export const SCALE_CLASS_NAMES = CLASS_BY_KEY;

export function scaleClass(key: ScaleKey): string {
  return styles[CLASS_BY_KEY[key]] ?? "";
}
