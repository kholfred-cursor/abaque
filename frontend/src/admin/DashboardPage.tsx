import { useAuth } from "../shared/auth/useAuth";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { fr } from "../shared/i18n/fr";
import styles from "./pages.module.css";

export function DashboardPage() {
  useDocumentTitle(fr.titles.dashboard);
  const { state } = useAuth();
  const organization = state.status === "authenticated" ? state.me.organization : null;
  return (
    <>
      <div className={styles.titleRow}>
        <h1>{fr.titles.dashboard}</h1>
        {organization && (
          <p className={styles.meta}>
            {fr.dashboard.planLabel} : {fr.dashboard.plan[organization.plan_code]}
          </p>
        )}
      </div>
      <section className={styles.empty} aria-labelledby="empty-title">
        <h2 id="empty-title">{fr.dashboard.empty}</h2>
        <p>{fr.dashboard.emptyHint}</p>
      </section>
    </>
  );
}
