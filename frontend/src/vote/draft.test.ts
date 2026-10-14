import { afterEach, describe, expect, it } from "vitest";
import { clearDraft, draftKey, loadDraft, saveDraft } from "./draft";

afterEach(() => localStorage.clear());

describe("local draft", () => {
  it("round-trips answers and the current group, per version", () => {
    saveDraft("v1", { answers: { i1: { color: "++", comment: "Bien" } }, group: 2 });
    expect(loadDraft("v1")).toEqual({
      answers: { i1: { color: "++", comment: "Bien" } },
      group: 2,
    });
    expect(loadDraft("v2")).toBeNull();
    clearDraft("v1");
    expect(loadDraft("v1")).toBeNull();
  });

  it("ignores corrupted or tampered content", () => {
    localStorage.setItem(draftKey("v1"), "{not json");
    expect(loadDraft("v1")).toBeNull();
    localStorage.setItem(
      draftKey("v1"),
      JSON.stringify({
        answers: { i1: { color: "+++", comment: "" }, i2: { color: "~", comment: "" } },
      }),
    );
    expect(loadDraft("v1")).toEqual({ answers: { i2: { color: "~", comment: "" } }, group: 0 });
  });
});

describe("storage stays confined to the draft (D039)", () => {
  const sources = import.meta.glob("/src/**/*.{ts,tsx}", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>;

  it("scans the sources", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(30);
  });

  it("uses localStorage and sessionStorage nowhere else", () => {
    const offenders = Object.entries(sources)
      .filter(([path]) => !/\/vote\/draft(\.test)?\.ts$/.test(path))
      .filter(([, code]) => /\b(localStorage|sessionStorage)\s*[.[]/.test(code))
      .map(([path]) => path);
    expect(offenders).toEqual([]);
  });
});
