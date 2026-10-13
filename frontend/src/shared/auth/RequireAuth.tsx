import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { Spinner } from "../ui/Spinner";
import { useAuth } from "./useAuth";

/** Protected pages: anonymous visitors go to /connexion, which brings them back after login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const location = useLocation();
  if (state.status === "loading") return <Spinner />;
  if (state.status === "anonymous") {
    const search = state.expired ? "?expired=1" : "";
    return <Navigate to={`/connexion${search}`} replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
