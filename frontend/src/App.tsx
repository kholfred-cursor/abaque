import { useMemo, type ReactNode } from "react";
import { ApiContext } from "./shared/api/ApiContext";
import { createApiClient, type ApiClient } from "./shared/api/client";
import { AuthProvider } from "./shared/auth/AuthProvider";

export function Providers({ children, client }: { children: ReactNode; client?: ApiClient }) {
  const api = useMemo(() => client ?? createApiClient(), [client]);
  return (
    <ApiContext.Provider value={api}>
      <AuthProvider>{children}</AuthProvider>
    </ApiContext.Provider>
  );
}
