import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiError, fakeApi, json, ME, type FakeApi } from "../../test/fakeApi";
import { renderApp } from "../../test/renderApp";

const VERSION = { id: "v1", label: "V1", status: "draft" as const, ballot_count: 0 };
const EVALUATION = {
  id: "e1",
  title: "Climat social",
  slug: "abcdefghjk",
  participation_mode: "anonymous",
  vote_preset: "agreement",
  created_at: "2026-10-14T08:00:00Z",
  versions: [VERSION],
  description: null,
  intro_md: null,
  outro_md: null,
  show_vote_example: false,
  anonymity_threshold: 3,
};
const SCALE = [
  { key: "++", label: "Tout à fait d'accord" },
  { key: "+", label: "Plutôt d'accord" },
  { key: "~", label: "Avis partagé, opinion mitigée" },
  { key: "-", label: "Plutôt pas d'accord" },
  { key: "--", label: "Pas du tout d'accord" },
];

function content(overrides: { editable?: boolean; revision?: number; items?: number } = {}) {
  const items = overrides.items ?? 2;
  return {
    version: {
      ...VERSION,
      evaluation_id: "e1",
      revision: overrides.revision ?? 1,
      editable: overrides.editable ?? true,
    },
    vote_preset: "agreement",
    groups: [
      {
        id: "g1",
        name: "Général",
        items: Array.from({ length: items }, (_, n) => ({
          id: `i${n + 1}`,
          short_name: `Item ${n + 1}`,
          statement: `Affirmation ${n + 1}.`,
        })),
      },
    ],
    color_labels: {},
    scale: SCALE,
  };
}

function signedIn(evaluation: object = EVALUATION): FakeApi {
  return fakeApi({
    "GET /api/auth/me": () => json(200, ME),
    "GET /api/evaluations": () => json(200, [evaluation]),
    "GET /api/evaluations/e1": () => json(200, evaluation),
    "GET /api/versions/v1": () => json(200, content()),
  });
}

async function bodyOf(api: FakeApi, route: string): Promise<unknown> {
  const request = [...api.calls]
    .reverse()
    .find((r) => `${r.method} ${new URL(r.url).pathname}` === route);
  return request ? await request.clone().json() : undefined;
}

afterEach(() => vi.restoreAllMocks());

describe("evaluation list and creation", () => {
  it("lists evaluations with the state of their current version", async () => {
    const open = { ...EVALUATION, versions: [{ ...VERSION, status: "open", ballot_count: 12 }] };
    renderApp("/", signedIn(open));
    const link = await screen.findByRole("link", { name: "Climat social" });
    expect(link.getAttribute("href")).toBe("/evaluations/e1");
    const row = link.closest("li") as HTMLElement;
    expect(within(row).getByText("Ouverte")).toBeTruthy();
    expect(within(row).getByText("12 réponses")).toBeTruthy();
  });

  it("creates an evaluation and opens its items", async () => {
    const api = signedIn();
    api.on("GET /api/evaluations", () => json(200, []));
    api.on("POST /api/evaluations", () => json(201, EVALUATION));
    const router = renderApp("/", api);

    await userEvent.click(await screen.findByRole("button", { name: "Nouvelle évaluation" }));
    const title = screen.getByLabelText("Titre de l'évaluation");
    await waitFor(() => expect(document.activeElement).toBe(title));
    await userEvent.click(screen.getByRole("button", { name: "Créer l'évaluation" }));
    expect(title.getAttribute("aria-invalid")).toBe("true");
    expect(api.count("POST /api/evaluations")).toBe(0);

    await userEvent.type(title, "  Climat social  ");
    await userEvent.click(screen.getByLabelText(/Score 1 à 5/));
    await userEvent.click(screen.getByRole("button", { name: "Créer l'évaluation" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/evaluations/e1/items"));
    expect(await bodyOf(api, "POST /api/evaluations")).toEqual({
      title: "Climat social",
      vote_preset: "score",
      participation_mode: "anonymous",
    });
  });

  it("explains a plan limit", async () => {
    const api = signedIn();
    api.on("POST /api/evaluations", () => apiError(403, "LIMIT_REACHED"));
    renderApp("/", api);
    await userEvent.click(await screen.findByRole("button", { name: "Nouvelle évaluation" }));
    await userEvent.type(screen.getByLabelText("Titre de l'évaluation"), "Deuxième");
    await userEvent.click(screen.getByRole("button", { name: "Créer l'évaluation" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Limite de votre offre atteinte.");
  });

  it("shows an error for an unknown evaluation", async () => {
    const api = signedIn();
    api.on("GET /api/evaluations/e1", () => apiError(404, "NOT_FOUND"));
    renderApp("/evaluations/e1", api);
    expect((await screen.findByRole("alert")).textContent).toBe("Élément introuvable.");
  });
});

describe("items editor", () => {
  it("adds, reorders and saves items in one request with the loaded revision", async () => {
    const api = signedIn();
    api.on("PUT /api/versions/v1/content", () => json(200, content({ revision: 2, items: 3 })));
    renderApp("/evaluations/e1/items", api);

    await screen.findByRole("group", { name: "Item 1" });
    const save = screen.getByRole("button", { name: "Enregistrer les items" });
    expect(save).toHaveProperty("disabled", true); // nothing to save yet

    await userEvent.click(screen.getByRole("button", { name: "+ Ajouter un item" }));
    const third = screen.getByRole("group", { name: "Item 3" });
    const shortName = within(third).getByLabelText(/Nom court/);
    await waitFor(() => expect(document.activeElement).toBe(shortName));
    await userEvent.type(shortName, "Charge");
    await userEvent.type(within(third).getByLabelText(/Affirmation/), "La charge est tenable.");
    await userEvent.click(screen.getByRole("button", { name: "Monter : Item 3" }));
    expect(screen.getByText(/Modifications non enregistrées/)).toBeTruthy();

    await userEvent.click(save);
    expect(await screen.findByText("Items enregistrés.")).toBeTruthy();
    expect(await bodyOf(api, "PUT /api/versions/v1/content")).toEqual({
      revision: 1,
      groups: [
        {
          id: "g1",
          name: "Général",
          items: [
            { id: "i1", short_name: "Item 1", statement: "Affirmation 1." },
            { short_name: "Charge", statement: "La charge est tenable." },
            { id: "i2", short_name: "Item 2", statement: "Affirmation 2." },
          ],
        },
      ],
      color_labels: {},
    });
  });

  it("points at the first invalid field instead of saving", async () => {
    const api = signedIn();
    renderApp("/evaluations/e1/items", api);
    const first = await screen.findByRole("group", { name: "Item 1" });
    await userEvent.clear(within(first).getByLabelText(/Affirmation/));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer les items" }));
    const statement = within(first).getByLabelText(/Affirmation/);
    await waitFor(() => expect(document.activeElement).toBe(statement));
    expect(statement.getAttribute("aria-invalid")).toBe("true");
    expect(api.count("PUT /api/versions/v1/content")).toBe(0);
  });

  it("reports a save made in another tab", async () => {
    const api = signedIn();
    api.on("PUT /api/versions/v1/content", () => apiError(409, "CONTENT_CONFLICT"));
    renderApp("/evaluations/e1/items", api);
    await userEvent.click(await screen.findByRole("button", { name: "Supprimer l'item : Item 2" }));
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer les items" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("modifiés ailleurs");
    expect(within(alert).getByRole("button", { name: "Recharger" })).toBeTruthy();
  });

  it("shows a frozen version read-only", async () => {
    const api = signedIn();
    api.on("GET /api/versions/v1", () => json(200, content({ editable: false })));
    renderApp("/evaluations/e1/items", api);
    expect(await screen.findByText(/Le contenu de cette version est figé/)).toBeTruthy();
    expect(screen.getByText("Affirmation 2.")).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("imports a CSV file, only once the draft is saved", async () => {
    const api = signedIn();
    api.on("POST /api/versions/v1/items/import", () =>
      json(200, content({ revision: 2, items: 3 })),
    );
    renderApp("/evaluations/e1/items", api);
    const file = new File(["short_name;statement\nA;B\n"], "items.csv", { type: "text/csv" });
    await userEvent.upload(await screen.findByLabelText("Fichier CSV"), file);
    await userEvent.click(screen.getByLabelText("Ajouter aux items actuels"));
    await userEvent.click(screen.getByRole("button", { name: "Importer" }));
    expect(await screen.findByText("3 items importés.")).toBeTruthy();
    expect(await bodyOf(api, "POST /api/versions/v1/items/import")).toEqual({
      revision: 1,
      csv: "short_name;statement\nA;B\n",
      mode: "append",
    });

    await userEvent.type(
      within(screen.getByRole("group", { name: "Item 1" })).getByLabelText(/Nom court/),
      "!",
    );
    expect(screen.getByRole("button", { name: "Importer" })).toHaveProperty("disabled", true);
    expect(
      screen.getByText("Enregistrez vos modifications avant d'importer un fichier."),
    ).toBeTruthy();
  });

  it("edits custom scale labels when the preset is custom", async () => {
    const api = signedIn({ ...EVALUATION, vote_preset: "custom" });
    api.on("PUT /api/versions/v1/content", () => json(200, content({ revision: 2 })));
    renderApp("/evaluations/e1/items", api);
    await userEvent.type(await screen.findByLabelText("++ — Tout à fait d'accord"), "Oui");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer les items" }));
    await screen.findByText("Items enregistrés.");
    expect(await bodyOf(api, "PUT /api/versions/v1/content")).toMatchObject({
      color_labels: { "++": "Oui" },
    });
  });
});

describe("versions", () => {
  it("opens a draft, then shows the public link and its QR code", async () => {
    const api = signedIn();
    api.on("POST /api/versions/v1/transitions", () => {
      api.on("GET /api/evaluations/e1", () =>
        json(200, { ...EVALUATION, versions: [{ ...VERSION, status: "open" }] }),
      );
      return json(200, { ...VERSION, status: "open" });
    });
    renderApp("/evaluations/e1/versions", api);
    expect(await screen.findByText(/Aucune version n'est ouverte/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Ouvrir le vote : V1" }));

    const link = await screen.findByRole("link", {
      name: `${window.location.origin}/v/abcdefghjk`,
    });
    expect(link.getAttribute("href")).toBe(`${window.location.origin}/v/abcdefghjk`);
    const qr = screen.getByRole("img", { name: "QR code du lien de vote" });
    expect(qr.querySelector("path")?.getAttribute("d")).toMatch(/^M\d/);
    expect(await bodyOf(api, "POST /api/versions/v1/transitions")).toEqual({ action: "open" });
  });

  it("asks before closing, and Escape cancels", async () => {
    const opened = { ...EVALUATION, versions: [{ ...VERSION, status: "open", ballot_count: 4 }] };
    const api = signedIn(opened);
    api.on("POST /api/versions/v1/transitions", () => json(200, { ...VERSION, status: "closed" }));
    renderApp("/evaluations/e1/versions", api);

    await userEvent.click(await screen.findByRole("button", { name: "Clore le vote : V1" }));
    const dialog = screen.getByRole("alertdialog");
    expect(document.activeElement).toBe(dialog);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(api.count("POST /api/versions/v1/transitions")).toBe(0);

    await userEvent.click(screen.getByRole("button", { name: "Clore le vote : V1" }));
    await userEvent.click(screen.getByRole("button", { name: "Clore le vote" }));
    await waitFor(() => expect(api.count("POST /api/versions/v1/transitions")).toBe(1));
    expect(await bodyOf(api, "POST /api/versions/v1/transitions")).toEqual({ action: "close" });
  });

  it("explains why an export is refused, and downloads it otherwise", async () => {
    const closed = { ...EVALUATION, versions: [{ ...VERSION, status: "closed", ballot_count: 2 }] };
    const api = signedIn(closed);
    api.on("GET /api/versions/v1/exports/ballots.csv", () =>
      json(409, { error: { code: "BELOW_THRESHOLD", message: "Il faut au moins 3 réponses." } }),
    );
    renderApp("/evaluations/e1/versions", api);
    await userEvent.click(
      await screen.findByRole("button", { name: "Exporter les réponses (CSV) : V1" }),
    );
    expect((await screen.findByRole("alert")).textContent).toBe("Il faut au moins 3 réponses.");

    const created = vi.fn(() => "blob:x");
    vi.stubGlobal(
      "URL",
      Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() }),
    );
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    api.on(
      "GET /api/versions/v1/exports/ballots.csv",
      () =>
        new Response("﻿ballot_ref;item_position\r\n", {
          status: 200,
          headers: {
            "Content-Type": "text/csv",
            "Content-Disposition": 'attachment; filename="abaque_abcdefghjk_V1_ballots.csv"',
          },
        }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Exporter les réponses (CSV) : V1" }));
    await waitFor(() => expect(click).toHaveBeenCalled());
    expect(created).toHaveBeenCalled();
  });
});

describe("evaluation settings", () => {
  it("saves the texts and the threshold", async () => {
    const api = signedIn();
    api.on("PATCH /api/evaluations/e1", () => json(200, EVALUATION));
    renderApp("/evaluations/e1", api);
    await userEvent.type(await screen.findByLabelText(/Texte d'accueil/), "Bienvenue");
    await userEvent.clear(screen.getByLabelText("Seuil d'anonymat (k)"));
    await userEvent.type(screen.getByLabelText("Seuil d'anonymat (k)"), "5");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));
    expect(await screen.findByText("Modifications enregistrées.")).toBeTruthy();
    expect(await bodyOf(api, "PATCH /api/evaluations/e1")).toMatchObject({
      title: "Climat social",
      intro_md: "Bienvenue",
      outro_md: null,
      anonymity_threshold: 5,
    });
  });

  it("deletes only after confirmation", async () => {
    const api = signedIn();
    api.on("DELETE /api/evaluations/e1", () => new Response(null, { status: 204 }));
    const router = renderApp("/evaluations/e1", api);
    await userEvent.click(await screen.findByRole("button", { name: "Supprimer l'évaluation" }));
    const dialog = screen.getByRole("alertdialog", { name: /Supprimer définitivement/ });
    expect(within(dialog).getByText(/irréversible/)).toBeTruthy();
    expect(api.count("DELETE /api/evaluations/e1")).toBe(0);
    await userEvent.click(within(dialog).getByRole("button", { name: "Supprimer définitivement" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });
});
