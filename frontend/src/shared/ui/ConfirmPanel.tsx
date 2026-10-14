import { useEffect, useId, useRef, type ReactNode } from "react";
import { fr } from "../i18n/fr";
import { Button } from "./Button";
import styles from "./ui.module.css";

/** Asks for confirmation in place (no modal): focus moves to the panel when it appears,
 * Escape or "Annuler" closes it. */
export function ConfirmPanel({
  title,
  children,
  confirmLabel,
  busy,
  onConfirm,
  onCancel,
}: {
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    ref.current?.focus(); // once, when the panel appears
  }, []);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);
  return (
    <div
      ref={ref}
      role="alertdialog"
      aria-labelledby={titleId}
      tabIndex={-1}
      className={styles.confirm}
    >
      <h2 id={titleId}>{title}</h2>
      {children}
      <div className={styles.confirmActions}>
        <Button className={styles.dangerButton} disabled={busy} onClick={onConfirm}>
          {confirmLabel}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {fr.dashboard.cancel}
        </Button>
      </div>
    </div>
  );
}
