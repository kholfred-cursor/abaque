import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useApi } from "../api/ApiContext";
import { SESSION_EXPIRED_EVENT } from "../api/client";
import { toApiError } from "../api/errors";
import { AuthContext, type AuthState } from "./AuthContext";

/** Authentication state comes from GET /api/auth/me only: nothing is kept in
 * localStorage or sessionStorage (cookies are HttpOnly). */
export function AuthProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const refreshMe = useCallback(async () => {
    const { data } = await api.GET("/api/auth/me");
    setState(
      data ? { status: "authenticated", me: data } : { status: "anonymous", expired: false },
    );
  }, [api]);

  useEffect(() => {
    let active = true;
    void api.GET("/api/auth/me").then(({ data }) => {
      if (active) {
        setState(
          data ? { status: "authenticated", me: data } : { status: "anonymous", expired: false },
        );
      }
    });
    return () => {
      active = false;
    };
  }, [api]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { data, error, response } = await api.POST("/api/auth/login", {
        body: { email, password },
      });
      if (!data) throw toApiError(response.status, error);
      setState({ status: "authenticated", me: data });
    },
    [api],
  );

  const logout = useCallback(async () => {
    await api.POST("/api/auth/logout");
    setState({ status: "anonymous", expired: false });
  }, [api]);

  const sessionExpired = useCallback(() => {
    setState((previous) => ({
      status: "anonymous",
      expired: previous.status === "authenticated",
    }));
  }, []);

  useEffect(() => {
    window.addEventListener(SESSION_EXPIRED_EVENT, sessionExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, sessionExpired);
  }, [sessionExpired]);

  const value = useMemo(
    () => ({ state, login, logout, refreshMe, sessionExpired }),
    [state, login, logout, refreshMe, sessionExpired],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
