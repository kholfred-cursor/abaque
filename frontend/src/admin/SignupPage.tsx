import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useApi } from "../shared/api/ApiContext";
import { toApiError } from "../shared/api/errors";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { useFormErrors } from "../shared/hooks/useFormErrors";
import { fr } from "../shared/i18n/fr";
import { Alert } from "../shared/ui/Alert";
import { Button } from "../shared/ui/Button";
import { Field, PasswordField } from "../shared/ui/Field";
import { AuthLayout } from "../shared/ui/Layout";
import styles from "./forms.module.css";

const FIELDS = ["organization", "email", "password"] as const;

export function SignupPage() {
  useDocumentTitle(fr.titles.signup);
  const api = useApi();
  const [values, setValues] = useState({ organization: "", email: "", password: "" });
  const [state, setState] = useState<"form" | "submitting" | "done" | "closed">("form");
  const organizationRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const { fieldErrors, globalError, alertRef, requireFilled, showError } = useFormErrors(FIELDS);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (
      state === "submitting" ||
      !requireFilled(values, {
        organization: organizationRef,
        email: emailRef,
        password: passwordRef,
      })
    )
      return;
    setState("submitting");
    try {
      const { error, response } = await api.POST("/api/auth/signup", {
        body: {
          organization_name: values.organization,
          email: values.email,
          password: values.password,
        },
      });
      if (response.status === 202) return setState("done");
      const apiError = toApiError(response.status, error);
      if (apiError.code === "SIGNUP_DISABLED") return setState("closed");
      throw apiError;
    } catch (error) {
      showError(error);
      setState("form");
    }
  }

  if (state === "done" || state === "closed") {
    return (
      <AuthLayout title={fr.titles.signup}>
        <Alert tone={state === "done" ? "success" : "notice"}>
          {state === "done" ? fr.signup.done : fr.signup.closed}
        </Alert>
        <Link to="/connexion">{fr.signup.login}</Link>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={fr.titles.signup}>
      <p>{fr.signup.intro}</p>
      {globalError && (
        <Alert tone="danger" ref={alertRef}>
          {globalError}
        </Alert>
      )}
      <form className={styles.form} onSubmit={(e) => void onSubmit(e)} noValidate>
        <Field
          ref={organizationRef}
          label={fr.fields.organization}
          hint={fr.fields.organizationHint}
          autoComplete="organization"
          value={values.organization}
          error={fieldErrors.organization}
          onChange={(e) => setValues({ ...values, organization: e.target.value })}
        />
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
          autoComplete="new-password"
          value={values.password}
          error={fieldErrors.password}
          onChange={(e) => setValues({ ...values, password: e.target.value })}
        />
        <Button type="submit" disabled={state === "submitting"}>
          {state === "submitting" ? fr.signup.submitting : fr.signup.submit}
        </Button>
      </form>
      <p>
        {fr.signup.haveAccount} <Link to="/connexion">{fr.signup.login}</Link>
      </p>
    </AuthLayout>
  );
}
