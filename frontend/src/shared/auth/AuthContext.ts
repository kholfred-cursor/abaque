import { createContext } from "react";
import type { components } from "../api/schema";

export type Me = components["schemas"]["MeResponse"];

export type AuthState =
  | { status: "loading" }
  | { status: "anonymous"; expired: boolean }
  | { status: "authenticated"; me: Me };

export interface AuthContextValue {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  sessionExpired: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
