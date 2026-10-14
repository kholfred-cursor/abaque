import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "./Markdown";

describe("Markdown subset", () => {
  it("renders paragraphs, breaks, lists, bold and italic", () => {
    const { container } = render(
      <Markdown text={"**Bienvenue** à tous.\nMerci *vraiment*.\n\n- un\n- deux"} />,
    );
    expect(container.innerHTML).toBe(
      "<p><strong>Bienvenue</strong> à tous.<br>Merci <em>vraiment</em>.</p><ul><li>un</li><li>deux</li></ul>",
    );
  });

  it("never interprets HTML or links", () => {
    const { container } = render(
      <Markdown text={'<img src=x onerror="alert(1)"> [ici](https://exemple.fr)'} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toContain("<img src=x");
  });
});
