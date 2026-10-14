import { describe, expect, it } from "vitest";
import {
  addGroup,
  addItem,
  fromContent,
  itemCount,
  moveGroup,
  moveItem,
  moveItemBefore,
  moveItemToGroup,
  removeGroup,
  removeItem,
  toPayload,
  updateItem,
  validate,
  type Draft,
} from "./editorState";

const content = [
  {
    id: "g1",
    name: "Management",
    items: [
      { id: "i1", short_name: "Écoute", statement: "Mon manager m'écoute." },
      { id: "i2", short_name: "Clarté", statement: "Les objectifs sont clairs." },
    ],
  },
  {
    id: "g2",
    name: "Outils",
    items: [{ id: "i3", short_name: "Outils", statement: "J'ai les outils." }],
  },
];

const names = (draft: Draft) =>
  draft.map((g) => `${g.name}:${g.items.map((i) => i.short_name).join(",")}`);
const keyOf = (draft: Draft, shortName: string) =>
  draft.flatMap((g) => g.items).find((i) => i.short_name === shortName)?.key ?? "";

describe("editor draft", () => {
  it("round-trips the server content and keeps ids", () => {
    const draft = fromContent(content);
    expect(toPayload(draft)).toEqual(content);
    expect(itemCount(draft)).toBe(3);
  });

  it("omits ids of new elements and trims the texts", () => {
    let draft = addGroup(fromContent([]), "  Nouveau  ");
    const added = addItem(draft, draft[0]?.key ?? "");
    draft = updateItem(added.draft, added.key, { short_name: " A ", statement: " B " });
    expect(toPayload(draft)).toEqual([
      { name: "Nouveau", items: [{ short_name: "A", statement: "B" }] },
    ]);
  });

  it("moves items within a group and across group boundaries", () => {
    let draft = fromContent(content);
    draft = moveItem(draft, keyOf(draft, "Clarté"), -1);
    expect(names(draft)).toEqual(["Management:Clarté,Écoute", "Outils:Outils"]);
    draft = moveItem(draft, keyOf(draft, "Écoute"), 1); // last of its group: goes down a group
    expect(names(draft)).toEqual(["Management:Clarté", "Outils:Écoute,Outils"]);
    draft = moveItem(draft, keyOf(draft, "Écoute"), -1); // first of its group: goes up
    expect(names(draft)).toEqual(["Management:Clarté,Écoute", "Outils:Outils"]);
    expect(moveItem(draft, keyOf(draft, "Clarté"), -1)).toBe(draft); // already first overall
  });

  it("supports drag and drop, group moves and removals", () => {
    let draft = fromContent(content);
    draft = moveItemBefore(draft, keyOf(draft, "Outils"), keyOf(draft, "Écoute"));
    expect(names(draft)).toEqual(["Management:Outils,Écoute,Clarté", "Outils:"]);
    draft = moveItemToGroup(draft, keyOf(draft, "Écoute"), draft[1]?.key ?? "");
    expect(names(draft)).toEqual(["Management:Outils,Clarté", "Outils:Écoute"]);
    draft = moveGroup(draft, draft[1]?.key ?? "", -1);
    expect(names(draft)).toEqual(["Outils:Écoute", "Management:Outils,Clarté"]);
    draft = removeItem(draft, keyOf(draft, "Outils"));
    draft = removeGroup(draft, draft[0]?.key ?? "");
    expect(names(draft)).toEqual(["Management:Clarté"]);
  });

  it("validates like the API", () => {
    let draft = addGroup([], " ");
    const added = addItem(draft, draft[0]?.key ?? "");
    draft = updateItem(added.draft, added.key, { short_name: "x".repeat(51), statement: "ok" });
    expect(validate(draft).map((e) => e.field)).toEqual(["name", "short_name"]);
  });
});
