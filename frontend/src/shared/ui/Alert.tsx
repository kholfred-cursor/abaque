import { forwardRef, type ReactNode } from "react";
import styles from "./ui.module.css";

type Tone = "danger" | "notice" | "success";

/** Message block. Errors use role="alert"; it is focusable so a form can move focus to it. */
export const Alert = forwardRef<HTMLDivElement, { tone: Tone; children: ReactNode }>(function Alert(
  { tone, children },
  ref,
) {
  return (
    <div
      ref={ref}
      tabIndex={-1}
      role={tone === "danger" ? "alert" : "status"}
      className={`${styles.alert} ${styles[tone]}`}
    >
      {children}
    </div>
  );
});

export function Banner({ children }: { children: ReactNode }) {
  return <div className={`${styles.alert} ${styles.notice} ${styles.banner}`}>{children}</div>;
}
