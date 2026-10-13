import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiError, fakeApi, json, ME } from "../../test/fakeApi";
import { createApiClient, readCookie } from "./client";
import { ApiError, messageFor, toApiError } from "./errors";

const BASE = "http://abaque.test";

beforeEach(() => {
  document.cookie = "abq_csrf=csrf-1; path=/";
});

describe("CSRF", () => {
  it("adds X-CSRF-Token on state-changing requests only", async () => {
    const api = fakeApi({
      "GET /api/auth/me": () => json(200, ME),
      "POST /api/auth/logout": () => json(204),
    });
    const client = createApiClient({ baseUrl: BASE, fetch: api.fetch });

    await client.GET("/api/auth/me");
    await client.POST("/api/auth/logout");

    expect(api.calls[0]?.headers.get("X-CSRF-Token")).toBeNull();
    expect(api.calls[1]?.headers.get("X-CSRF-Token")).toBe("csrf-1");
  });

  it("reads cookies by exact name", () => {
    expect(readCookie("abq_csrf", "x_abq_csrf=no; abq_csrf=yes%3D")).toBe("yes=");
  });
});

describe("session refresh", () => {
  it("refreshes once on 401 and replays the request once", async () => {
    let expired = true;
    const api = fakeApi({
      "GET /api/auth/me": () => (expired ? apiError(401, "NOT_AUTHENTICATED") : json(200, ME)),
      "POST /api/auth/refresh": () => {
        expired = false;
        document.cookie = "abq_csrf=csrf-2; path=/";
        return json(204);
      },
    });
    const client = createApiClient({ baseUrl: BASE, fetch: api.fetch });

    const { data } = await client.GET("/api/auth/me");

    expect(data?.email).toBe(ME.email);
    expect(api.count("POST /api/auth/refresh")).toBe(1);
    expect(api.count("GET /api/auth/me")).toBe(2);
  });

  it("shares ONE refresh between concurrent requests", async () => {
    let expired = true;
    const api = fakeApi({
      "GET /api/auth/me": () => (expired ? apiError(401, "NOT_AUTHENTICATED") : json(200, ME)),
      "GET /api/auth/sessions": () =>
        expired ? apiError(401, "NOT_AUTHENTICATED") : json(200, []),
      "POST /api/auth/refresh": async () => {
        await new Promise((r) => setTimeout(r, 10));
        expired = false;
        return json(204);
      },
    });
    const client = createApiClient({ baseUrl: BASE, fetch: api.fetch });

    const results = await Promise.all([
      client.GET("/api/auth/me"),
      client.GET("/api/auth/sessions"),
      client.GET("/api/auth/me"),
    ]);

    expect(results.every((r) => r.response.ok)).toBe(true);
    expect(api.count("POST /api/auth/refresh")).toBe(1);
  });

  it("treats a 409 from refresh (another tab rotated) as success and replays", async () => {
    let calls = 0;
    const api = fakeApi({
      "GET /api/auth/me": () =>
        calls++ === 0 ? apiError(401, "NOT_AUTHENTICATED") : json(200, ME),
      "POST /api/auth/refresh": () => apiError(409, "SESSION_ROTATED"),
    });
    const client = createApiClient({ baseUrl: BASE, fetch: api.fetch });

    const { data } = await client.GET("/api/auth/me");

    expect(data?.id).toBe(ME.id);
  });

  it("announces an expired session when refresh fails, without looping", async () => {
    const onSessionExpired = vi.fn();
    const api = fakeApi({
      "GET /api/auth/me": () => apiError(401, "NOT_AUTHENTICATED"),
      "POST /api/auth/refresh": () => apiError(401, "SESSION_REVOKED"),
    });
    const client = createApiClient({ baseUrl: BASE, fetch: api.fetch, onSessionExpired });

    const { response } = await client.GET("/api/auth/me");

    expect(response.status).toBe(401);
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
    expect(api.count("POST /api/auth/refresh")).toBe(1);
  });

  it("does not try to refresh when no session was ever opened (no CSRF cookie)", async () => {
    document.cookie = "abq_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
    const onSessionExpired = vi.fn();
    const api = fakeApi({ "GET /api/auth/me": () => apiError(401, "NOT_AUTHENTICATED") });
    const client = createApiClient({ baseUrl: BASE, fetch: api.fetch, onSessionExpired });

    await client.GET("/api/auth/me");

    expect(api.count("POST /api/auth/refresh")).toBe(0);
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
  });

  it("never refreshes on a failed login", async () => {
    const api = fakeApi({ "POST /api/auth/login": () => apiError(401, "INVALID_CREDENTIALS") });
    const client = createApiClient({ baseUrl: BASE, fetch: api.fetch });

    await client.POST("/api/auth/login", { body: { email: "a@b.fr", password: "x" } });

    expect(api.count("POST /api/auth/refresh")).toBe(0);
  });

  it("replays a POST with its body and the rotated CSRF token", async () => {
    let expired = true;
    const api = fakeApi({
      "POST /api/auth/password/change": () =>
        expired ? apiError(401, "NOT_AUTHENTICATED") : json(204),
      "POST /api/auth/refresh": () => {
        expired = false;
        document.cookie = "abq_csrf=csrf-rotated; path=/";
        return json(204);
      },
    });
    const client = createApiClient({ baseUrl: BASE, fetch: api.fetch });

    await client.POST("/api/auth/password/change", {
      body: { current_password: "old-one", new_password: "new-one" },
    });

    const replay = api.calls.filter((c) => c.url.endsWith("/password/change"))[1];
    expect(replay?.headers.get("X-CSRF-Token")).toBe("csrf-rotated");
    expect(await replay?.json()).toEqual({ current_password: "old-one", new_password: "new-one" });
  });
});

describe("errors", () => {
  it("maps known codes to French messages and hides unknown server messages", () => {
    expect(messageFor("INVALID_CREDENTIALS")).toBe("Adresse e-mail ou mot de passe incorrect.");
    expect(messageFor("SOMETHING_NEW")).toContain("erreur inattendue");
    const error = toApiError(403, { error: { code: "LIMIT_REACHED_UNKNOWN", message: "raw" } });
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).not.toContain("raw");
    expect(toApiError(500, "not json").code).toBe("GENERIC");
  });
});
