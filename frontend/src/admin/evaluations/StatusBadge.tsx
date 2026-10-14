import { fr } from "../../shared/i18n/fr";
import styles from "./evaluations.module.css";

export type VersionStatus = keyof typeof fr.statuses;

export function StatusBadge({ status }: { status: VersionStatus }) {
  return (
    <span className={`${styles.status} ${styles[`status_${status}`] ?? ""}`}>
      {fr.statuses[status]}
    </span>
  );
}
