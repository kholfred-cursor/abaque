import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useApi } from "../shared/api/ApiContext";
import { toApiError } from "../shared/api/errors";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { useFormErrors } from "../shared/hooks/useFormErrors";
import { useUrlToken } from "../shared/hooks/useUrlToken";
import { fr } from "../shared/i18n/fr";
import { Alert } from "../shared/ui/Alert";
import { Button } from "../shared/ui/Button";
import { PasswordField } from "../shared/ui/Field";
import { AuthLayout } from "../shared/ui/Layout";
import styles from "./forms.module.css";

const FIELDS = ["password"] as const;

export function ResetPasswordPage() {
  useDocumentTitle(fr.titles.reset);
  const api = useApi();
  const token = useUrlToken();
  const [values, setValues] = useState({ password: "" });
  const [state, setState] = useState<"form" | "submitting" | "done">("form");
  const passwordRef = useRef<HTMLInputElement>(null);
  const { fieldErrors, globalError, alertRef, requireFilled, showError } = useFormErrors(FIELDS);

  if (token === null) {
    return (
      <AuthLayout title={fr.titles.reset}>
        <Alert tone="danger">{fr.verify.missing}</Alert>
        <Link to="/mot-de-passe-oublie">{fr.titles.forgot}</Link>
      </AuthLayout>
    );
  }
  const resetToken = token;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (state === "submitting" || !requireFilled(values, { password: passwordRef })) return;
    setState("submitting");
    try {
      const { error, response } = await api.POST("/api/auth/password/reset", {
        body: { token: resetToken, password: values.password },
      });
      if (response.status !== 204) throw toApiError(response.status, error);
      setState("done");
    } catch (error) {
      showError(error);
      setState("form");
    }
  }

  return (
    <AuthLayout title={fr.titles.reset}>
      {state === "done" ? (
        <>
          <Alert tone="success">{fr.reset.done}</Alert>
          <Link to="/connexion">{fr.reset.login}</Link>
        </>
      ) : (
        <>
          <p>{fr.reset.intro}</p>
          {globalError && (
            <Alert tone="danger" ref={alertRef}>
              {globalError}
            </Alert>
          )}
          <form className={styles.form} onSubmit={(e) => void onSubmit(e)} noValidate>
            <PasswordField
              ref={passwordRef}
              label={fr.fields.newPassword}
              autoComplete="new-password"
              value={values.password}
              error={fieldErrors.password}
              onChange={(e) => setValues({ password: e.target.value })}
            />
            <Button type="submit" disabled={state === "submitting"}>
              {state === "submitting" ? fr.reset.submitting : fr.reset.submit}
            </Button>
          </form>
        </>
      )}
    </AuthLayout>
  );
}
