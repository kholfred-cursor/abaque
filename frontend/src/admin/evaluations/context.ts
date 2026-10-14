import { useOutletContext } from "react-router";
import type { components } from "../../shared/api/schema";

export type EvaluationDetail = components["schemas"]["EvaluationDetail"];
export type VersionSummary = components["schemas"]["VersionSummary"];

export interface EvaluationOutlet {
  evaluation: EvaluationDetail;
  /** Re-read the evaluation (after a transition, a save...). */
  reload: () => void;
}

export function useEvaluation(): EvaluationOutlet {
  return useOutletContext<EvaluationOutlet>();
}

/** The version shown by default: the open one, otherwise the most recent. */
export function currentVersion(versions: readonly VersionSummary[]): VersionSummary | undefined {
  return versions.find((v) => v.status === "open") ?? versions[versions.length - 1];
}

export function publicLink(slug: string): string {
  return `${window.location.origin}/v/${slug}`;
}
