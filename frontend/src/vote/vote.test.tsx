import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { apiError, fakeApi, json, type FakeApi } from "../test/fakeApi";
import { renderApp } from "../test/renderApp";
import { clearDraft, loadDraft, saveDraft } from "./draft";

const SCALE = [
  { key: "++", label: "Tout à fait d'accord" },
  { key: "+", label: "Plutôt d'accord" },
  { key: "~", label: "Avis partagé, opinion mitigée" },
  { key: "-", label: "Plutôt pas d'accord" },
  { key: "--", label: "Pas du tout d'accord" },
];
const PAGE = {
  title: "Climat social",
  status: "open",
  version_id: "v1",
  already_voted: false,
  intro_md: "**Bienvenue**. Cela prend 3 minutes.",
  outro_md: "Résultats présentés jeudi.",
  show_vote_example: true,
  scale: SCALE,
  groups: [
    {
      id: "g1",
      name: "Organisation",
      items: [
        { id: "i1", short_name: "Charge", statement: "Ma charge de travail est raisonnable." },
        { id: "i2", short_name: "Outils", statement: "J'ai les outils nécessaires." },
      ],
    },
    {
      id: "g2",
      name: "Management",
      items: [{ id: "i3", short_name: "Écoute", statement: "Mon responsable m'écoute." }],
    },
  ],
};

function voter(page: object = PAGE): FakeApi {
  return fakeApi({
    "GET /api/auth/me": () => apiError(401, "NOT_AUTHENTICATED"),
    "GET /api/public/v/abcdefghjk": () => json(200, page),
  });
}

const card = (statement: string) => screen.getByRole("article", { name: statement }) as HTMLElement;

async function choose(statement: string, label: RegExp) {
  await userEvent.click(within(card(statement)).getByRole("radio", { name: label }));
}

afterEach(() => clearDraft("v1"));

describe("voting page", () => {
  it("votes group by group, reviews, sends only the answers, then thanks", async () => {
    const api = voter();
    api.on("POST /api/public/v/abcdefghjk/ballots", () => json(201, { status: "recorded" }));
    renderApp("/v/abcdefghjk", api);

    expect(await screen.findByRole("heading", { name: "Climat social" })).toBeTruthy();
    expect(screen.getByText("Bienvenue").tagName).toBe("STRONG");
    expect(screen.getByRole("heading", { name: "Comment répondre" })).toBeTruthy();
    expect(screen.getByText(/ne relie vos réponses à votre identité/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Commencer" }));

    expect(await screen.findByRole("heading", { name: "Organisation" })).toBeTruthy();
    const progress = screen.getByRole("progressbar", { name: "Votre progression" });
    expect(progress.getAttribute("aria-valuetext")).toBe("0 sur 3 répondus");

    await choose("Ma charge de travail est raisonnable.", /Plutôt pas d'accord/);
    const first = card("Ma charge de travail est raisonnable.");
    await userEvent.click(within(first).getByRole("button", { name: "Ajouter un commentaire" }));
    expect(within(first).getByText(/Ne mentionnez ni nom/)).toBeTruthy();
    await userEvent.type(
      within(first).getByLabelText("Commentaire (facultatif)"),
      "  Trop de réunions  ",
    );
    expect(progress.getAttribute("aria-valuetext")).toBe("1 sur 3 répondus");

    await userEvent.click(screen.getByRole("button", { name: "Suivant" }));
    expect(await screen.findByRole("heading", { name: "Management" })).toBeTruthy();
    await choose("Mon responsable m'écoute.", /Tout à fait d'accord/);
    await userEvent.click(screen.getByRole("button", { name: "Vérifier et envoyer" }));

    expect(await screen.findByRole("heading", { name: "Avant d'envoyer" })).toBeTruthy();
    expect(screen.getByText("Vous avez répondu à 2 affirmations sur 3.")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Répondre : J'ai les outils nécessaires." }),
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Envoyer mes réponses" }));

    expect(
      await screen.findByRole("heading", { name: "Merci, vos réponses ont été enregistrées." }),
    ).toBeTruthy();
    expect(screen.getByText("Résultats présentés jeudi.")).toBeTruthy();
    const sent = api.calls.find((r) => r.method === "POST");
    expect(await sent?.json()).toEqual({
      version_id: "v1",
      votes: [
        { item_id: "i1", color_key: "-", comment: "Trop de réunions" },
        { item_id: "i3", color_key: "++" },
      ],
    });
    expect(loadDraft("v1")).toBeNull(); // draft deleted after acceptance
  });

  it("keeps a draft across a reload and resumes it", async () => {
    saveDraft("v1", { answers: { i3: { color: "+", comment: "" } }, group: 1 });
    renderApp("/v/abcdefghjk", voter());
    expect(await screen.findByText(/Vos réponses en cours sur cet appareil/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Reprendre mes réponses" }));
    expect(await screen.findByRole("heading", { name: "Management" })).toBeTruthy();
    const radio = within(card("Mon responsable m'écoute.")).getByRole("radio", {
      name: /Plutôt d'accord/,
    });
    expect(radio).toHaveProperty("checked", true);

    await choose("Mon responsable m'écoute.", /Avis partagé/);
    await waitFor(() => expect(loadDraft("v1")?.answers.i3?.color).toBe("~"));
  });

  it("refuses a ballot sent after closing and keeps the answers readable", async () => {
    const api = voter();
    api.on("POST /api/public/v/abcdefghjk/ballots", () => apiError(409, "VERSION_CLOSED"));
    renderApp("/v/abcdefghjk", api);
    await userEvent.click(await screen.findByRole("button", { name: "Commencer" }));
    await choose("J'ai les outils nécessaires.", /Plutôt d'accord/);
    await userEvent.click(screen.getByRole("button", { name: "Suivant" }));
    await userEvent.click(await screen.findByRole("button", { name: "Vérifier et envoyer" }));
    await userEvent.click(await screen.findByRole("button", { name: "Envoyer mes réponses" }));

    expect((await screen.findByRole("alert")).textContent).toBe(
      "Cette consultation est close, votre réponse n'a pas été enregistrée.",
    );
    const answers = screen.getByRole("region", { name: "Vos réponses" });
    expect(within(answers).getByText("Plutôt d'accord")).toBeTruthy();
    expect(loadDraft("v1")?.answers.i2?.color).toBe("+"); // the draft stays
  });

  it("asks for at least one answer before sending", async () => {
    const api = voter();
    renderApp("/v/abcdefghjk", api);
    await userEvent.click(await screen.findByRole("button", { name: "Commencer" }));
    await userEvent.click(screen.getByRole("button", { name: "Suivant" }));
    await userEvent.click(await screen.findByRole("button", { name: "Vérifier et envoyer" }));
    await userEvent.click(await screen.findByRole("button", { name: "Envoyer mes réponses" }));
    expect(
      await screen.findByText("Répondez à au moins une affirmation avant d'envoyer."),
    ).toBeTruthy();
    expect(api.count("POST /api/public/v/abcdefghjk/ballots")).toBe(0);
  });

  it("tells a voter who already answered from this device", async () => {
    renderApp("/v/abcdefghjk", voter({ ...PAGE, already_voted: true }));
    expect(
      await screen.findByRole("heading", { name: "Vous avez déjà répondu depuis cet appareil." }),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Commencer" })).toBeNull();
  });

  it("explains an unknown link", async () => {
    const api = voter();
    api.on("GET /api/public/v/abcdefghjk", () => apiError(404, "NOT_FOUND"));
    renderApp("/v/abcdefghjk", api);
    expect((await screen.findByRole("alert")).textContent).toContain("n'existe pas");
  });
});
