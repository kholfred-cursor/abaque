/** Pure editing operations on the content of a version (groups and items).
 *
 * The editor works on a local draft and saves it in one request (D038). Every operation
 * returns a new array: React state is never mutated. ``key`` is a local identity for
 * rendering and drag and drop; ``id`` is the server id, absent for a new element.
 */
import type { components } from "../../shared/api/schema";

type GroupView = components["schemas"]["GroupView"];
type GroupInput = components["schemas"]["GroupInput"];

export const SHORT_NAME_MAX = 50;
export const STATEMENT_MAX = 2000;
export const GROUP_NAME_MAX = 200;

export interface DraftItem {
  key: string;
  id?: string;
  short_name: string;
  statement: string;
}

export interface DraftGroup {
  key: string;
  id?: string;
  name: string;
  items: DraftItem[];
}

export type Draft = DraftGroup[];

let sequence = 0;
export function newKey(prefix: string): string {
  sequence += 1;
  return `${prefix}-${sequence}`;
}

export function fromContent(groups: readonly GroupView[]): Draft {
  return groups.map((group) => ({
    key: newKey("g"),
    id: group.id,
    name: group.name,
    items: group.items.map((item) => ({
      key: newKey("i"),
      id: item.id,
      short_name: item.short_name,
      statement: item.statement,
    })),
  }));
}

export function toPayload(draft: Draft): GroupInput[] {
  return draft.map((group) => ({
    ...(group.id ? { id: group.id } : {}),
    name: group.name.trim(),
    items: group.items.map((item) => ({
      ...(item.id ? { id: item.id } : {}),
      short_name: item.short_name.trim(),
      statement: item.statement.trim(),
    })),
  }));
}

export function itemCount(draft: Draft): number {
  return draft.reduce((total, group) => total + group.items.length, 0);
}

export function addGroup(draft: Draft, name: string): Draft {
  return [...draft, { key: newKey("g"), name, items: [] }];
}

export function renameGroup(draft: Draft, groupKey: string, name: string): Draft {
  return draft.map((group) => (group.key === groupKey ? { ...group, name } : group));
}

export function removeGroup(draft: Draft, groupKey: string): Draft {
  return draft.filter((group) => group.key !== groupKey);
}

export function moveGroup(draft: Draft, groupKey: string, delta: -1 | 1): Draft {
  const index = draft.findIndex((group) => group.key === groupKey);
  const target = index + delta;
  if (index < 0 || target < 0 || target >= draft.length) return draft;
  const next = [...draft];
  const [moved] = next.splice(index, 1);
  if (moved) next.splice(target, 0, moved);
  return next;
}

export function addItem(draft: Draft, groupKey: string): { draft: Draft; key: string } {
  const key = newKey("i");
  return {
    key,
    draft: draft.map((group) =>
      group.key === groupKey
        ? { ...group, items: [...group.items, { key, short_name: "", statement: "" }] }
        : group,
    ),
  };
}

export function updateItem(
  draft: Draft,
  itemKey: string,
  patch: Partial<Pick<DraftItem, "short_name" | "statement">>,
): Draft {
  return draft.map((group) => ({
    ...group,
    items: group.items.map((item) => (item.key === itemKey ? { ...item, ...patch } : item)),
  }));
}

export function removeItem(draft: Draft, itemKey: string): Draft {
  return draft.map((group) => ({
    ...group,
    items: group.items.filter((item) => item.key !== itemKey),
  }));
}

/** Move an item one step up or down; at a group boundary it changes group. */
export function moveItem(draft: Draft, itemKey: string, delta: -1 | 1): Draft {
  const flat = draft.flatMap((group) => group.items.map((item) => ({ group: group.key, item })));
  const index = flat.findIndex((entry) => entry.item.key === itemKey);
  if (index < 0) return draft;
  const groupIndex = draft.findIndex((group) => group.key === flat[index]?.group);
  const group = draft[groupIndex];
  if (!group) return draft;
  const position = group.items.findIndex((item) => item.key === itemKey);
  const target = position + delta;
  if (target >= 0 && target < group.items.length) {
    const items = [...group.items];
    const [moved] = items.splice(position, 1);
    if (moved) items.splice(target, 0, moved);
    return draft.map((g) => (g.key === group.key ? { ...g, items } : g));
  }
  const neighbour = draft[groupIndex + delta];
  if (!neighbour) return draft;
  const item = group.items[position];
  if (!item) return draft;
  return draft.map((g) => {
    if (g.key === group.key) return { ...g, items: g.items.filter((i) => i.key !== itemKey) };
    if (g.key === neighbour.key) {
      return { ...g, items: delta < 0 ? [...g.items, item] : [item, ...g.items] };
    }
    return g;
  });
}

/** Place an item just before another one (drag and drop), possibly in another group. */
export function moveItemBefore(draft: Draft, itemKey: string, beforeKey: string): Draft {
  if (itemKey === beforeKey) return draft;
  const item = draft.flatMap((group) => group.items).find((i) => i.key === itemKey);
  if (!item) return draft;
  const without = removeItem(draft, itemKey);
  return without.map((group) => {
    const index = group.items.findIndex((i) => i.key === beforeKey);
    if (index < 0) return group;
    const items = [...group.items];
    items.splice(index, 0, item);
    return { ...group, items };
  });
}

export function moveItemToGroup(draft: Draft, itemKey: string, groupKey: string): Draft {
  const item = draft.flatMap((group) => group.items).find((i) => i.key === itemKey);
  if (!item) return draft;
  return removeItem(draft, itemKey).map((group) =>
    group.key === groupKey ? { ...group, items: [...group.items, item] } : group,
  );
}

export interface DraftError {
  key: string;
  field: "name" | "short_name" | "statement";
  message: string;
}

/** The same limits as the API, checked before saving so errors point at the field. */
export function validate(draft: Draft): DraftError[] {
  const errors: DraftError[] = [];
  for (const group of draft) {
    const name = group.name.trim();
    if (!name || name.length > GROUP_NAME_MAX) {
      errors.push({ key: group.key, field: "name", message: `1 à ${GROUP_NAME_MAX} caractères.` });
    }
    for (const item of group.items) {
      const shortName = item.short_name.trim();
      if (!shortName || shortName.length > SHORT_NAME_MAX) {
        errors.push({
          key: item.key,
          field: "short_name",
          message: `1 à ${SHORT_NAME_MAX} caractères.`,
        });
      }
      const statement = item.statement.trim();
      if (!statement || statement.length > STATEMENT_MAX) {
        errors.push({
          key: item.key,
          field: "statement",
          message: `1 à ${STATEMENT_MAX} caractères.`,
        });
      }
    }
  }
  return errors;
}
