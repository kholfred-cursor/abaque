import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { useApi } from "../shared/api/ApiContext";
import { call } from "../shared/api/call";
import { ApiError } from "../shared/api/errors";
import type { components } from "../shared/api/schema";
import { useAuth } from "../shared/auth/useAuth";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { fr } from "../shared/i18n/fr";
import { Alert } from "../shared/ui/Alert";
import { Button } from "../shared/ui/Button";
import { Field, RadioGroup } from "../shared/ui/Field";
import { Spinner } from "../shared/ui/Spinner";
import { currentVersion } from "./evaluations/context";
import evaluationStyles from "./evaluations/evaluations.module.css";
import { StatusBadge } from "./evaluations/StatusBadge";
import styles from "./pages.module.css";

type Summary = components["schemas"]["EvaluationSummary"];
type Preset = Summary["vote_preset"];

const PRESETS: readonly { value: Preset; label: string; hint: string }[] = [
  { value: "agreement", label: fr.presets.agreement, hint: fr.presets.agreementHint },
  { value: "score", label: fr.presets.score, hint: fr.presets.scoreHint },
  { value: "custom", label: fr.presets.custom, hint: fr.presets.customHint },
];

function CreateForm({ onCancel }: { onCancel: () => void }) {
  const api = useApi();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [preset, setPreset] = useState<Preset>("agreement");
  const [busy, setBusy] = useState(false);
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const alertRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setFieldError(fr.fields.required);
      titleRef.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await call(
        api.POST("/api/evaluations", {
          body: { title: title.trim(), vote_preset: preset, participation_mode: "anonymous" },
        }),
      );
      void navigate(`/evaluations/${created.id}/items`);
    } catch (reason) {
      setBusy(false);
      setError(reason instanceof ApiError ? reason.message : fr.errors.GENERIC);
      requestAnimationFrame(() => alertRef.current?.focus());
    }
  }

  return (
    <form className={evaluationStyles.createForm} onSubmit={(e) => void submit(e)} noValidate>
      <h2>{fr.dashboard.create}</h2>
      {error && (
        <Alert tone="danger" ref={alertRef}>
          {error}
        </Alert>
      )}
      <Field
        ref={titleRef}
        label={fr.dashboard.createTitle}
        hint={fr.dashboard.createTitleHint}
        value={title}
        maxLength={300}
        error={fieldError}
        onChange={(e) => {
          setTitle(e.target.value);
          setFieldError(undefined);
        }}
      />
      <RadioGroup
        legend={fr.evaluation.preset}
        name="preset"
        value={preset}
        options={PRESETS}
        onChange={setPreset}
      />
      <div className={evaluationStyles.actions}>
        <Button type="submit" disabled={busy}>
          {busy ? fr.dashboard.creating : fr.dashboard.createSubmit}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {fr.dashboard.cancel}
        </Button>
      </div>
    </form>
  );
}

export function DashboardPage() {
  useDocumentTitle(fr.titles.dashboard);
  const api = useApi();
  const { state } = useAuth();
  const organization = state.status === "authenticated" ? state.me.organization : null;
  const [evaluations, setEvaluations] = useState<Summary[] | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let active = true;
    void call(api.GET("/api/evaluations")).then(
      (data) => {
        if (active) setEvaluations(data);
      },
      () => {
        if (active) setEvaluations([]);
      },
    );
    return () => {
      active = false;
    };
  }, [api]);

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
      {creating ? (
        <CreateForm onCancel={() => setCreating(false)} />
      ) : (
        <div>
          <Button onClick={() => setCreating(true)}>{fr.dashboard.create}</Button>
        </div>
      )}
      {evaluations === null ? (
        <Spinner />
      ) : evaluations.length === 0 ? (
        !creating && (
          <section className={styles.empty} aria-labelledby="empty-title">
            <h2 id="empty-title">{fr.dashboard.empty}</h2>
            <p>{fr.dashboard.emptyHint}</p>
          </section>
        )
      ) : (
        <ul className={evaluationStyles.evaluations}>
          {evaluations.map((evaluation) => {
            const version = currentVersion(evaluation.versions);
            return (
              <li key={evaluation.id} className={evaluationStyles.evaluation}>
                <Link to={`/evaluations/${evaluation.id}`}>{evaluation.title}</Link>
                <span className={styles.meta}>
                  {version ? fr.dashboard.ballots(version.ballot_count) : ""}
                </span>
                <div className={evaluationStyles.evaluationMeta}>
                  {version ? (
                    <>
                      <span>{version.label}</span>
                      <StatusBadge status={version.status} />
                    </>
                  ) : (
                    fr.dashboard.noVersion
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
