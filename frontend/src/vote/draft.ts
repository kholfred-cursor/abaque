/** The voter's local draft (D039): the ONLY use of browser storage in the application.
 *
 * It keeps the answers in progress so a reload does not lose them; there is no offline
 * mode. One key per version, deleted after the server has accepted the ballot. If the
 * server refuses the ballot (vote closed), the draft stays readable. Storage may be
 * unavailable (private mode, quota): every access is guarded and failure is silent.
 */
import type { ScaleKey } from "../shared/design/scale";

export interface Answer {
  color: ScaleKey;
  comment: string;
}

export interface VoteDraft {
  answers: Record<string, Answer>;
  group: number;
}

const PREFIX = "abaque:brouillon:";
const KEYS = new Set<string>(["++", "+", "~", "-", "--"]);

export const draftKey = (versionId: string) => `${PREFIX}${versionId}`;

function isAnswer(value: unknown): value is Answer {
  if (typeof value !== "object" || value === null) return false;
  const answer = value as Record<string, unknown>;
  return (
    typeof answer.color === "string" && KEYS.has(answer.color) && typeof answer.comment === "string"
  );
}

export function loadDraft(versionId: string): VoteDraft | null {
  try {
    const raw = localStorage.getItem(draftKey(versionId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { answers?: unknown; group?: unknown };
    if (typeof parsed.answers !== "object" || parsed.answers === null) return null;
    const answers: Record<string, Answer> = {};
    for (const [itemId, answer] of Object.entries(parsed.answers)) {
      if (isAnswer(answer)) answers[itemId] = { color: answer.color, comment: answer.comment };
    }
    return { answers, group: typeof parsed.group === "number" ? parsed.group : 0 };
  } catch {
    return null;
  }
}

export function saveDraft(versionId: string, draft: VoteDraft): void {
  try {
    localStorage.setItem(draftKey(versionId), JSON.stringify(draft));
  } catch {
    // Storage full or disabled: the vote still works, only the reload safety is lost.
  }
}

export function clearDraft(versionId: string): void {
  try {
    localStorage.removeItem(draftKey(versionId));
  } catch {
    // nothing to clean
  }
}
