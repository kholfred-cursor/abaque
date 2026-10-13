import { useCallback, useEffect, useState } from "react";
import { useApi } from "../shared/api/ApiContext";
import type { components } from "../shared/api/schema";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { fr } from "../shared/i18n/fr";
import { Alert } from "../shared/ui/Alert";
import { Button } from "../shared/ui/Button";
import { Spinner } from "../shared/ui/Spinner";
import styles from "./pages.module.css";

type Session = components["schemas"]["SessionResponse"];

const dateFormat = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short" });

export function SessionsPage() {
  useDocumentTitle(fr.titles.sessions);
  const api = useApi();
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    const { data } = await api.GET("/api/auth/sessions");
    setSessions(data ?? []);
  }, [api]);

  useEffect(() => {
    let active = true;
    void api.GET("/api/auth/sessions").then(({ data }) => {
      if (active) setSessions(data ?? []);
    });
    return () => {
      active = false;
    };
  }, [api]);

  async function revoke(id: string) {
    await api.DELETE("/api/auth/sessions/{session_id}", { params: { path: { session_id: id } } });
    setMessage(fr.sessions.revoked);
    await load();
  }

  async function revokeOthers() {
    await api.DELETE("/api/auth/sessions");
    setMessage(fr.sessions.othersRevoked);
    await load();
  }

  if (sessions === null) return <Spinner />;
  const others = sessions.filter((s) => !s.current);

  return (
    <>
      <h1>{fr.titles.sessions}</h1>
      <p>{fr.sessions.intro}</p>
      {message && <Alert tone="success">{message}</Alert>}
      <ul className={styles.list}>
        {sessions.map((session) => (
          <li key={session.id} className={styles.row}>
            <div>
              <p className={styles.rowTitle}>
                {session.device ?? fr.sessions.unknownDevice}
                {session.current && <span className={styles.badge}>{fr.sessions.current}</span>}
              </p>
              <p className={styles.meta}>
                {fr.sessions.created} {dateFormat.format(new Date(session.created_at))}
                {", "}
                {session.last_used_at
                  ? `${fr.sessions.lastUsed.toLowerCase()} ${dateFormat.format(new Date(session.last_used_at))}`
                  : fr.sessions.never}
              </p>
            </div>
            {!session.current && (
              <Button variant="secondary" onClick={() => void revoke(session.id)}>
                {fr.sessions.revoke}
              </Button>
            )}
          </li>
        ))}
      </ul>
      {others.length > 0 ? (
        <div>
          <Button variant="secondary" onClick={() => void revokeOthers()}>
            {fr.sessions.revokeOthers}
          </Button>
        </div>
      ) : (
        <p className={styles.meta}>{fr.sessions.onlyCurrent}</p>
      )}
    </>
  );
}
