import { fr } from "../i18n/fr";
import styles from "./ui.module.css";

export function Spinner() {
  return (
    <p className={styles.spinner} role="status">
      {fr.loading}
    </p>
  );
}
