import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useParams } from "react-router";
import { useApi } from "../../shared/api/ApiContext";
import { call } from "../../shared/api/call";
import { ApiError } from "../../shared/api/errors";
import { useDocumentTitle } from "../../shared/hooks/useDocumentTitle";
import { fr } from "../../shared/i18n/fr";
import { Alert } from "../../shared/ui/Alert";
import { Spinner } from "../../shared/ui/Spinner";
import type { EvaluationDetail, EvaluationOutlet } from "./context";
import styles from "./evaluations.module.css";

export function EvaluationLayout() {
  const { evaluationId = "" } = useParams();
  const api = useApi();
  const [evaluation, setEvaluation] = useState<EvaluationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState(0);
  useDocumentTitle(evaluation?.title ?? fr.loading);

  useEffect(() => {
    let active = true;
    void call(
      api.GET("/api/evaluations/{evaluation_id}", {
        params: { path: { evaluation_id: evaluationId } },
      }),
    ).then(
      (data) => {
        if (active) setEvaluation(data);
      },
      (reason: unknown) => {
        if (active) setError(reason instanceof ApiError ? reason.message : fr.errors.GENERIC);
      },
    );
    return () => {
      active = false;
    };
  }, [api, evaluationId, token]);

  const reload = useCallback(() => setToken((n) => n + 1), []);

  if (error) {
    return (
      <>
        <Alert tone="danger">{error}</Alert>
        <Link to="/">{fr.evaluation.back}</Link>
      </>
    );
  }
  if (!evaluation) return <Spinner />;
  const outlet: EvaluationOutlet = { evaluation, reload };
  const base = `/evaluations/${evaluation.id}`;
  return (
    <>
      <Link to="/" className={styles.back}>
        ← {fr.evaluation.back}
      </Link>
      <h1>{evaluation.title}</h1>
      <nav aria-label={fr.evaluation.tabs} className={styles.tabs}>
        <NavLink to={base} end className={styles.tab ?? ""}>
          {fr.titles.evaluationSettings}
        </NavLink>
        <NavLink to={`${base}/items`} className={styles.tab ?? ""}>
          {fr.titles.items}
        </NavLink>
        <NavLink to={`${base}/versions`} className={styles.tab ?? ""}>
          {fr.titles.versions}
        </NavLink>
      </nav>
      <Outlet context={outlet} />
    </>
  );
}
