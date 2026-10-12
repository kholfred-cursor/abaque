import { renderToString } from "react-dom/server";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";
import { routes } from "./routes";

function renderAt(path: string): string {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return renderToString(<RouterProvider router={router} />);
}

describe("routes du squelette", () => {
  it("affiche l'accueil", () => {
    expect(renderAt("/")).toContain("Abaque");
  });

  it("affiche la page participant publique", () => {
    expect(renderAt("/v/demo")).toContain("Bientôt disponible");
  });

  it("affiche une 404 pour un chemin inconnu", () => {
    expect(renderAt("/nimporte-quoi")).toContain("Page introuvable");
  });
});
