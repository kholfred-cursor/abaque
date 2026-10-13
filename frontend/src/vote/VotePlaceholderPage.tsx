import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { fr } from "../shared/i18n/fr";
import { ParticipantLayout } from "../shared/ui/Layout";

/** Public participant page: mobile-first, independent from the facilitator session. */
export function VotePlaceholderPage() {
  useDocumentTitle(fr.titles.vote);
  return (
    <ParticipantLayout>
      <h1>{fr.vote.soon}</h1>
      <p>{fr.vote.soonHint}</p>
    </ParticipantLayout>
  );
}
