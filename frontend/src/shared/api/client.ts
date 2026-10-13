import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

/**
 * Typed API client (generated types, see `npm run gen:api`).
 * - CSRF: X-CSRF-Token copied from the abq_csrf cookie on every state-changing request.
 * - Refresh: on a 401, ONE shared POST /api/auth/refresh for all concurrent requests,
 *   then each original request is replayed once. A 409 from refresh means another tab
 *   already rotated the session (D029): its cookies are ours too, so we just replay.
 */
export type ApiClient = ReturnType<typeof createClient<paths>>;

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const NO_REFRESH_PATHS = new Set([
  "/api/auth/login",
  "/api/auth/refresh",
  "/api/auth/signup",
  "/api/auth/logout",
]);
const RETRY_HEADER = "X-Abaque-Retry";

export function readCookie(name: string, cookieString: string = document.cookie): string | null {
  for (const part of cookieString.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

function withCsrf(request: Request): Request {
  if (!UNSAFE_METHODS.has(request.method)) return request;
  const token = readCookie("abq_csrf");
  if (token) request.headers.set("X-CSRF-Token", token);
  return request;
}

export const SESSION_EXPIRED_EVENT = "abaque:session-expired";

function announceSessionExpired(): void {
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
}

export interface ClientOptions {
  baseUrl?: string;
  fetch?: typeof globalThis.fetch;
  onSessionExpired?: () => void;
}

export function createApiClient(options: ClientOptions = {}): ApiClient {
  const baseUrl = options.baseUrl ?? window.location.origin;
  const fetchImpl = options.fetch ?? ((input, init) => globalThis.fetch(input, init));
  const pending = new Map<string, Request>();
  let refreshing: Promise<boolean> | null = null;

  function refreshOnce(): Promise<boolean> {
    refreshing ??= (async () => {
      try {
        const response = await fetchImpl(
          withCsrf(
            new Request(`${baseUrl}/api/auth/refresh`, { method: "POST", credentials: "include" }),
          ),
        );
        return response.status === 204 || response.status === 409;
      } catch {
        return false;
      }
    })().finally(() => {
      refreshing = null;
    });
    return refreshing;
  }

  const middleware: Middleware = {
    onRequest({ request, id }) {
      const prepared = withCsrf(request);
      pending.set(id, prepared.clone());
      return prepared;
    },
    async onResponse({ request, response, id }) {
      const original = pending.get(id);
      pending.delete(id);
      const path = new URL(request.url).pathname;
      if (
        response.status !== 401 ||
        original === undefined ||
        NO_REFRESH_PATHS.has(path) ||
        request.headers.has(RETRY_HEADER)
      ) {
        return undefined;
      }
      // No abq_csrf cookie means no session was ever opened in this browser (it is set
      // with the refresh cookie at login): nothing to renew, no pointless refresh call.
      if (readCookie("abq_csrf") === null || !(await refreshOnce())) {
        (options.onSessionExpired ?? announceSessionExpired)();
        return undefined;
      }
      const replay = withCsrf(new Request(original, { credentials: "include" }));
      replay.headers.set(RETRY_HEADER, "1");
      const retried = await fetchImpl(replay);
      if (retried.status === 401) (options.onSessionExpired ?? announceSessionExpired)();
      return retried;
    },
  };

  const client = createClient<paths>({ baseUrl, credentials: "include", fetch: fetchImpl });
  client.use(middleware);
  return client;
}
