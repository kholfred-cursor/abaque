import { useState, type ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router";
import { useApi } from "../api/ApiContext";
import { useAuth } from "../auth/useAuth";
import { fr } from "../i18n/fr";
import { Button } from "./Button";
import styles from "./layout.module.css";
import { Banner } from "./Alert";
import { ScaleMark } from "./ScaleMark";

export function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.auth}>
      <ScaleMark variant="column" />
      <main className={styles.authMain}>
        <p className={styles.wordmark}>{fr.app.name}</p>
        <h1>{title}</h1>
        {children}
      </main>
    </div>
  );
}

function VerifyEmailBanner() {
  const api = useApi();
  const [sent, setSent] = useState(false);
  return (
    <Banner>
      <span>{sent ? fr.verify.resent : fr.verify.banner}</span>
      {!sent && (
        <Button
          variant="secondary"
          onClick={() => {
            void api.POST("/api/auth/verify-email/resend").then(() => setSent(true));
          }}
        >
          {fr.verify.resend}
        </Button>
      )}
    </Banner>
  );
}

export function AppLayout() {
  const { state, logout } = useAuth();
  const me = state.status === "authenticated" ? state.me : null;
  return (
    <>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <Link to="/" className={styles.brand}>
            {fr.app.name}
          </Link>
          {me?.organization && <span className={styles.org}>{me.organization.name}</span>}
          <nav aria-label={fr.nav.main} className={styles.nav}>
            <NavLink to="/" end className={styles.navLink ?? ""}>
              {fr.nav.dashboard}
            </NavLink>
            <NavLink to="/compte/sessions" className={styles.navLink ?? ""}>
              {fr.nav.sessions}
            </NavLink>
          </nav>
          <Button variant="quiet" onClick={() => void logout()}>
            {fr.nav.logout}
          </Button>
        </div>
        <ScaleMark variant="strip" />
      </header>
      <main className={styles.content}>
        {me && !me.email_verified && <VerifyEmailBanner />}
        <Outlet />
      </main>
    </>
  );
}

export function ParticipantLayout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.participant}>
      <ScaleMark variant="strip" />
      <main className={styles.participantMain}>{children}</main>
    </div>
  );
}
