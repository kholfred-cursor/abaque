import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useApi } from "../shared/api/ApiContext";
import { toApiError } from "../shared/api/errors";
import { useAuth } from "../shared/auth/useAuth";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { useUrlToken } from "../shared/hooks/useUrlToken";
import { fr } from "../shared/i18n/fr";
import { Alert } from "../shared/ui/Alert";
import { AuthLayout } from "../shared/ui/Layout";

export function VerifyEmailPage() {
  useDocumentTitle(fr.titles.verifyEmail);
  const api = useApi();
  const { refreshMe } = useAuth();
  const token = useUrlToken();
  const sent = useRef(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(
    token === null ? { ok: false, message: fr.verify.missing } : null,
  );

  useEffect(() => {
    // The token is single-use: StrictMode's double effect must not send it twice.
    if (token === null || sent.current) return;
    sent.current = true;
    void (async () => {
      const { error, response } = await api.POST("/api/auth/verify-email", { body: { token } });
      if (response.status === 204) {
        setResult({ ok: true, message: fr.verify.done });
        await refreshMe();
      } else {
        setResult({ ok: false, message: toApiError(response.status, error).message });
      }
    })();
  }, [api, refreshMe, token]);

  return (
    <AuthLayout title={fr.titles.verifyEmail}>
      {result === null ? (
        <p role="status">{fr.verify.checking}</p>
      ) : (
        <Alert tone={result.ok ? "success" : "danger"}>{result.message}</Alert>
      )}
      {result?.ok && <Link to="/">{fr.verify.continue}</Link>}
    </AuthLayout>
  );
}
