import { scale } from "../design/scale";
import { scaleClass } from "../design/scaleClass";
import styles from "./layout.module.css";

/** The five colours of the Régnier scale, each with its symbol: Abaque's signature. */
export function ScaleMark({ variant }: { variant: "column" | "strip" }) {
  return (
    <div className={variant === "column" ? styles.column : styles.strip} aria-hidden="true">
      {scale.map((color) => (
        <span key={color.key} className={`${styles.cell} ${scaleClass(color.key)}`}>
          {variant === "column" ? color.symbol : null}
        </span>
      ))}
    </div>
  );
}
