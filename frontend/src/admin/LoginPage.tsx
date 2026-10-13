import { useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router";
import { useAuth } from "../shared/auth/useAuth";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { useFormErrors } from "../shared/hooks/useFormErrors";
import { fr } from "../shared/i18n/fr";
import { Alert } from "../shared/ui/Alert";
import { Button } from "../shared/ui/Button";
import { Field, PasswordField } from "../shared/ui/Field";
import { AuthLayout } from "../shared/ui/Layout";
import styles from "./forms.module.css";

const FIELDS = ["email", "password"] as const;

export function LoginPage() {
  useDocumentTitle(fr.titles.login);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const [values, setValues] = useState({ email: "", password: "" });
  const [submitting, setSubmitting] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const { fieldErrors, globalError, alertRef, requireFilled, showError } = useFormErrors(FIELDS);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || !requireFilled(values, { email: emailRef, password: passwordRef })) return;
    setSubmitting(true);
    try {
      await login(values.email, values.password);
      navigate(from, { replace: true });
    } catch (error) {
      showError(error);
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title={fr.titles.login}>
      <p>{fr.login.intro}</p>
      {params.get("expired") === "1" && !globalError && (
        <Alert tone="notice">{fr.login.expired}</Alert>
      )}
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
          onChange={(e) => setValues({ ...values, email: e.target.value })}
        />
        <PasswordField
          ref={passwordRef}
          label={fr.fields.password}
          autoComplete="current-password"
          value={values.password}
          error={fieldErrors.password}
          onChange={(e) => setValues({ ...values, password: e.target.value })}
        />
        <Button type="submit" disabled={submitting}>
          {submitting ? fr.login.submitting : fr.login.submit}
        </Button>
      </form>
      <p className={styles.links}>
        <Link to="/mot-de-passe-oublie">{fr.login.forgot}</Link>
        <span>
          {fr.login.noAccount} <Link to="/inscription">{fr.login.signup}</Link>
        </span>
      </p>
    </AuthLayout>
  );
}
