import { useCallback, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { useApi } from "../../shared/api/ApiContext";
import { call } from "../../shared/api/call";
import { ApiError } from "../../shared/api/errors";
import { fr } from "../../shared/i18n/fr";
import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { ConfirmPanel } from "../../shared/ui/ConfirmPanel";
import { Field, RadioGroup, TextAreaField } from "../../shared/ui/Field";
import { useEvaluation, type EvaluationDetail } from "./context";
import styles from "./evaluations.module.css";

type Preset = EvaluationDetail["vote_preset"];
const PRESETS: readonly { value: Preset; label: string; hint: string }[] = [
  { value: "agreement", label: fr.presets.agreement, hint: fr.presets.agreementHint },
  { value: "score", label: fr.presets.score, hint: fr.presets.scoreHint },
  { value: "custom", label: fr.presets.custom, hint: fr.presets.customHint },
];

const messageOf = (reason: unknown) =>
  reason instanceof ApiError ? reason.message : fr.errors.GENERIC;

export function EvaluationSettingsPage() {
  const { evaluation, reload } = useEvaluation();
  const api = useApi();
  const navigate = useNavigate();
  const [title, setTitle] = useState(evaluation.title);
  const [description, setDescription] = useState(evaluation.description ?? "");
  const [intro, setIntro] = useState(evaluation.intro_md ?? "");
  const [outro, setOutro] = useState(evaluation.outro_md ?? "");
  const [preset, setPreset] = useState<Preset>(evaluation.vote_preset);
  const [showExample, setShowExample] = useState(evaluation.show_vote_example);
  const [threshold, setThreshold] = useState(String(evaluation.anonymity_threshold));
  const [thresholdError, setThresholdError] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "danger" | "success"; text: string } | null>(null);
  const [titleError, setTitleError] = useState<string | undefined>();
  const [confirming, setConfirming] = useState(false);
  const messageRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const deleteButtonRef = useRef<HTMLButtonElement>(null);
  const path = { params: { path: { evaluation_id: evaluation.id } } };

  function show(tone: "danger" | "success", text: string) {
    setMessage({ tone, text });
    requestAnimationFrame(() => messageRef.current?.focus());
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) {
      setTitleError(fr.fields.required);
      titleRef.current?.focus();
      return;
    }
    const k = Number(threshold);
    if (!Number.isInteger(k) || k < evaluation.anonymity_threshold || k > 50) {
      setThresholdError(fr.evaluation.thresholdError(evaluation.anonymity_threshold));
      return;
    }
    setBusy(true);
    try {
      await call(
        api.PATCH("/api/evaluations/{evaluation_id}", {
          ...path,
          body: {
            title: title.trim(),
            description: description.trim() || null,
            intro_md: intro.trim() || null,
            outro_md: outro.trim() || null,
            vote_preset: preset,
            show_vote_example: showExample,
            anonymity_threshold: k,
          },
        }),
      );
      show("success", fr.evaluation.saved);
      reload();
    } catch (reason) {
      show("danger", messageOf(reason));
    } finally {
      setBusy(false);
    }
  }

  async function duplicate() {
    try {
      const copy = await call(api.POST("/api/evaluations/{evaluation_id}/duplicate", path));
      void navigate(`/evaluations/${copy.id}`);
    } catch (reason) {
      show("danger", messageOf(reason));
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await call(api.DELETE("/api/evaluations/{evaluation_id}", path));
      void navigate("/");
    } catch (reason) {
      setBusy(false);
      setConfirming(false);
      show("danger", messageOf(reason));
    }
  }

  const cancelDelete = useCallback(() => {
    setConfirming(false);
    requestAnimationFrame(() => deleteButtonRef.current?.focus());
  }, []);

  return (
    <>
      {message && (
        <Alert tone={message.tone} ref={messageRef}>
          {message.text}
        </Alert>
      )}
      <form className={styles.form} onSubmit={(e) => void save(e)} noValidate>
        <Field
          ref={titleRef}
          label={fr.evaluation.title}
          value={title}
          maxLength={300}
          error={titleError}
          onChange={(e) => {
            setTitle(e.target.value);
            setTitleError(undefined);
          }}
        />
        <TextAreaField
          label={fr.evaluation.description}
          hint={fr.evaluation.descriptionHint}
          value={description}
          maxLength={2000}
          onChange={(e) => setDescription(e.target.value)}
        />
        <TextAreaField
          label={fr.evaluation.intro}
          hint={fr.evaluation.introHint}
          value={intro}
          maxLength={10000}
          onChange={(e) => setIntro(e.target.value)}
        />
        <TextAreaField
          label={fr.evaluation.outro}
          hint={fr.evaluation.outroHint}
          value={outro}
          maxLength={10000}
          onChange={(e) => setOutro(e.target.value)}
        />
        <RadioGroup
          legend={fr.evaluation.preset}
          name="preset"
          value={preset}
          options={PRESETS}
          onChange={setPreset}
        />
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={showExample}
            onChange={(e) => setShowExample(e.target.checked)}
          />
          {fr.evaluation.showExample}
        </label>
        <div className={styles.narrow}>
          <Field
            label={fr.evaluation.threshold}
            type="number"
            min={evaluation.anonymity_threshold}
            max={50}
            value={threshold}
            error={thresholdError}
            onChange={(e) => {
              setThreshold(e.target.value);
              setThresholdError(undefined);
            }}
          />
        </div>
        <p className={styles.toolbarStatus}>{fr.evaluation.thresholdHint}</p>
        <div className={styles.actions}>
          <Button type="submit" disabled={busy}>
            {busy ? fr.evaluation.saving : fr.evaluation.save}
          </Button>
          <Button variant="secondary" onClick={() => void duplicate()}>
            {fr.evaluation.duplicate}
          </Button>
        </div>
      </form>
      <section className={styles.dangerZone}>
        {confirming ? (
          <ConfirmPanel
            title={fr.evaluation.deleteTitle}
            confirmLabel={busy ? fr.evaluation.deleting : fr.evaluation.deleteConfirm}
            busy={busy}
            onConfirm={() => void remove()}
            onCancel={cancelDelete}
          >
            <p>{fr.evaluation.deleteText}</p>
            <p>{fr.evaluation.deleteExportHint}</p>
          </ConfirmPanel>
        ) : (
          <div>
            <Button variant="secondary" ref={deleteButtonRef} onClick={() => setConfirming(true)}>
              {fr.evaluation.delete}
            </Button>
          </div>
        )}
      </section>
    </>
  );
}
