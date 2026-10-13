import { useState } from "react";

/** Reads ?token= once, then removes it from the address bar and history (a token must not
 * linger in the URL, the history or a shared screenshot). */
export function useUrlToken(): string | null {
  const [token] = useState<string | null>(() => {
    const url = new URL(window.location.href);
    const value = url.searchParams.get("token");
    if (value !== null) {
      url.searchParams.delete("token");
      window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
    }
    return value;
  });
  return token;
}
