import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useApi } from "../shared/api/ApiContext";
import { toApiError } from "../shared/api/errors";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { useFormErrors } from "../shared/hooks/useFormErrors";
import { fr } from "../shared/i18n/fr";
import { Alert } from "../shared/ui/Alert";
import { Button } from "../shared/ui/Button";
import { Field } from "../shared/ui/Field";
import { AuthLayout } from "../shared/ui/Layout";
import styles from "./forms.module.css";

const FIELDS = ["email"] as const;

export function ForgotPasswordPage() {
  useDocumentTitle(fr.titles.forgot);
  const api = useApi();
  const [values, setValues] = useState({ email: "" });
  const [state, setState] = useState<"form" | "submitting" | "done">("form");
  const emailRef = useRef<HTMLInputElement>(null);
  const { fieldErrors, globalError, alertRef, requireFilled, showError } = useFormErrors(FIELDS);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (state === "submitting" || !requireFilled(values, { email: emailRef })) return;
    setState("submitting");
    try {
      const { error, response } = await api.POST("/api/auth/password/forgot", {
        body: { email: values.email },
      });
      if (response.status !== 202) throw toApiError(response.status, error);
      setState("done");
    } catch (error) {
      showError(error);
      setState("form");
    }
  }

  return (
    <AuthLayout title={fr.titles.forgot}>
      {state === "done" ? (
        <Alert tone="success">{fr.forgot.done}</Alert>
      ) : (
        <>
          <p>{fr.forgot.intro}</p>
          {globalError && (
            <Alert tone="danger" ref={alertRef}>
              {globalError}
            </Alert>
          )}
          <form className={styles.form} onSubmit={(e) => void onSubmit(e)} noValidate>
            <Field
              ref={emailRef}
              label={fr.fields.email}
              type="email"
              autoComplete="email"
              inputMode="email"
              value={values.email}
              error={fieldErrors.email}
              onChange={(e) => setValues({ email: e.target.value })}
            />
            <Button type="submit" disabled={state === "submitting"}>
              {state === "submitting" ? fr.forgot.submitting : fr.forgot.submit}
            </Button>
          </form>
        </>
      )}
      <Link to="/connexion">{fr.forgot.back}</Link>
    </AuthLayout>
  );
}
