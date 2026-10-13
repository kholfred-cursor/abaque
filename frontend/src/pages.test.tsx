import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import { Providers } from "./App";
import { buildRoutes } from "./routes";
import { createApiClient } from "./shared/api/client";
import { apiError, fakeApi, json, ME, type FakeApi } from "./test/fakeApi";

function renderApp(path: string, api: FakeApi, { strict = false } = {}) {
  const router = createMemoryRouter(buildRoutes(false), { initialEntries: [path] });
  const client = createApiClient({ baseUrl: "http://abaque.test", fetch: api.fetch });
  const tree = (
    <Providers client={client}>
      <RouterProvider router={router} />
    </Providers>
  );
  render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  return router;
}

const anonymous = () =>
  fakeApi({
    "GET /api/auth/me": () => apiError(401, "NOT_AUTHENTICATED"),
    "POST /api/auth/refresh": () => apiError(401, "SESSION_REVOKED"),
  });

describe("authentication flow", () => {
  it("redirects an anonymous visitor to the login page, then back after login", async () => {
    const api = anonymous();
    api.on("POST /api/auth/login", () => json(200, ME));
    api.on("GET /api/auth/sessions", () => json(200, []));
    const router = renderApp("/compte/sessions", api);

    await screen.findByRole("heading", { name: "Connexion" });
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), ME.email);
    await userEvent.type(screen.getByLabelText("Mot de passe"), "Correct-Horse-42");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    await screen.findByRole("heading", { name: "Sessions actives" });
    expect(router.state.location.pathname).toBe("/compte/sessions");
  });

  it("flags empty fields and focuses the first one", async () => {
    renderApp("/connexion", anonymous());
    await userEvent.click(await screen.findByRole("button", { name: "Se connecter" }));

    const email = screen.getByLabelText("Adresse e-mail");
    expect(email).toHaveProperty("ariaInvalid", "true");
    expect(document.activeElement).toBe(email);
    expect(email.getAttribute("aria-describedby")).toBeTruthy();
  });

  it("shows a generic French error on bad credentials and moves focus to it", async () => {
    const api = anonymous();
    api.on("POST /api/auth/login", () => apiError(401, "INVALID_CREDENTIALS"));
    renderApp("/connexion", api);

    await userEvent.type(await screen.findByLabelText("Adresse e-mail"), "x@example.com");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "wrong-password");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Adresse e-mail ou mot de passe incorrect.");
    await waitFor(() => expect(document.activeElement).toBe(alert));
    expect(api.count("POST /api/auth/refresh")).toBe(0); // no session cookie: never refreshes
  });

  it("lets the password be shown and hidden", async () => {
    renderApp("/connexion", anonymous());
    const password = await screen.findByLabelText("Mot de passe");
    expect(password.getAttribute("type")).toBe("password");
    const toggle = screen.getByRole("button", { name: "Afficher le mot de passe" });
    expect(toggle.getAttribute("aria-pressed")).toBe("false");
    await userEvent.click(toggle);
    expect(password.getAttribute("type")).toBe("text");
    expect(toggle.getAttribute("aria-pressed")).toBe("true");
    await userEvent.click(toggle);
    expect(password.getAttribute("type")).toBe("password");
    expect(password.getAttribute("autocomplete")).toBe("current-password");
  });
});

describe("account pages", () => {
  it("shows a neutral confirmation after signup", async () => {
    const api = anonymous();
    api.on("POST /api/auth/signup", () => json(202));
    renderApp("/inscription", api);

    await userEvent.type(
      await screen.findByLabelText("Nom de votre organisation"),
      "Cabinet Delta",
    );
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), "fred@example.com");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "Correct-Horse-42");
    await userEvent.click(screen.getByRole("button", { name: "Créer mon compte" }));

    expect((await screen.findByRole("status")).textContent).toContain(
      "Si cette adresse peut être utilisée",
    );
    expect(screen.getByLabelText).toBeDefined();
  });

  it("says when signups are closed", async () => {
    const api = anonymous();
    api.on("POST /api/auth/signup", () => apiError(403, "SIGNUP_DISABLED"));
    renderApp("/inscription", api);
    await userEvent.type(await screen.findByLabelText("Nom de votre organisation"), "X");
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), "a@example.com");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "Correct-Horse-42");
    await userEvent.click(screen.getByRole("button", { name: "Créer mon compte" }));
    expect((await screen.findByRole("status")).textContent).toContain("inscriptions sont fermées");
  });

  it("sends the email token once (even in StrictMode) and removes it from the URL", async () => {
    window.history.replaceState(null, "", "/verifier-email?token=secret-token-1234567890");
    const api = anonymous();
    api.on("POST /api/auth/verify-email", () => json(204));
    renderApp("/verifier-email", api, { strict: true });

    expect(await screen.findByText("Votre adresse e-mail est confirmée.")).toBeTruthy();
    expect(api.count("POST /api/auth/verify-email")).toBe(1);
    expect(await api.calls.find((c) => c.url.endsWith("/verify-email"))?.json()).toEqual({
      token: "secret-token-1234567890",
    });
    expect(window.location.search).toBe("");
  });

  it("keeps the reset form usable when the new password is refused", async () => {
    window.history.replaceState(null, "", "/reinitialiser?token=reset-token-1234567890");
    const api = anonymous();
    api.on("POST /api/auth/password/reset", () => apiError(422, "PASSWORD_POLICY"));
    renderApp("/reinitialiser", api);

    const field = await screen.findByLabelText("Nouveau mot de passe");
    expect(field.getAttribute("autocomplete")).toBe("new-password");
    expect(
      screen.getByText("12 caractères minimum, différent de votre adresse e-mail."),
    ).toBeTruthy();
    await userEvent.type(field, "short");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer le mot de passe" }));

    expect((await screen.findByRole("alert")).textContent).toContain("ne respecte pas la règle");
    expect(window.location.search).toBe("");
  });
});

describe("signed-in pages", () => {
  const signedIn = (overrides: Partial<typeof ME> = {}) =>
    fakeApi({ "GET /api/auth/me": () => json(200, { ...ME, ...overrides }) });

  it("shows the empty dashboard with the organisation and plan", async () => {
    renderApp("/", signedIn());
    expect(await screen.findByRole("heading", { name: "Mes évaluations" })).toBeTruthy();
    expect(screen.getByText("Cabinet Delta")).toBeTruthy();
    expect(screen.getByText("Offre : Essai")).toBeTruthy();
    expect(screen.getByText("Vous n'avez pas encore d'évaluation.")).toBeTruthy();
  });

  it("asks unverified owners to confirm their email and can resend it", async () => {
    const api = signedIn({ email_verified: false });
    api.on("POST /api/auth/verify-email/resend", () => json(202));
    renderApp("/", api);

    await userEvent.click(await screen.findByRole("button", { name: "Renvoyer l'e-mail" }));
    expect(
      await screen.findByText("Un nouvel e-mail de confirmation vous a été envoyé."),
    ).toBeTruthy();
    expect(api.calls.at(-1)?.headers.get("X-CSRF-Token")).toBeNull(); // no cookie in this test
  });

  it("lists sessions, marks the current one and closes another", async () => {
    let sessions = [
      {
        id: "s1",
        created_at: "2026-10-13T08:00:00Z",
        last_used_at: null,
        device: "Firefox · Windows",
        current: true,
      },
      {
        id: "s2",
        created_at: "2026-10-12T08:00:00Z",
        last_used_at: "2026-10-12T09:00:00Z",
        device: "Safari · iOS",
        current: false,
      },
    ];
    const api = signedIn();
    api.on("GET /api/auth/sessions", () => json(200, sessions));
    api.on("DELETE /api/auth/sessions/s2", () => {
      sessions = sessions.filter((s) => s.id !== "s2");
      return json(204);
    });
    renderApp("/compte/sessions", api);

    expect(await screen.findByText("Cette session")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Fermer" }));
    expect(await screen.findByText("Session fermée.")).toBeTruthy();
    expect(screen.queryByText("Safari · iOS")).toBeNull();
    expect(screen.getByText("Aucune autre session ouverte.")).toBeTruthy();
  });

  it("returns to the login page with an expiry notice when the session cannot be renewed", async () => {
    document.cookie = "abq_csrf=csrf-1; path=/";
    let meCalls = 0;
    const api = fakeApi({
      "GET /api/auth/me": () =>
        meCalls++ === 0 ? json(200, ME) : apiError(401, "NOT_AUTHENTICATED"),
      "GET /api/auth/sessions": () => apiError(401, "NOT_AUTHENTICATED"),
      "POST /api/auth/refresh": () => apiError(401, "SESSION_REVOKED"),
    });
    const router = renderApp("/compte/sessions", api);

    await waitFor(() => expect(router.state.location.pathname).toBe("/connexion"));
    expect(router.state.location.search).toBe("?expired=1");
    expect(await screen.findByText("Votre session a expiré. Reconnectez-vous.")).toBeTruthy();
  });
});

describe("public pages", () => {
  it("serves the participant page without any facilitator session", async () => {
    const api = anonymous();
    renderApp("/v/atelier-2026", api);
    expect(
      await screen.findByRole("heading", { name: "Ce vote n'est pas encore ouvert." }),
    ).toBeTruthy();
    expect(document.title).toBe("Vote | Abaque");
  });

  it("shows a 404 page", async () => {
    renderApp("/nulle-part", anonymous());
    expect(await screen.findByRole("heading", { name: "Page introuvable" })).toBeTruthy();
  });

  it("does not expose the development tokens page outside development", async () => {
    renderApp("/dev/tokens", fakeApi({ "GET /api/auth/me": () => json(200, ME) }));
    expect(await screen.findByRole("heading", { name: "Page introuvable" })).toBeTruthy();
  });
});
