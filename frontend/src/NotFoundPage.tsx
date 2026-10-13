import { Link } from "react-router";
import { useDocumentTitle } from "./shared/hooks/useDocumentTitle";
import { fr } from "./shared/i18n/fr";
import { ParticipantLayout } from "./shared/ui/Layout";

export function NotFoundPage() {
  useDocumentTitle(fr.titles.notFound);
  return (
    <ParticipantLayout>
      <h1>{fr.titles.notFound}</h1>
      <p>{fr.notFound.text}</p>
      <Link to="/">{fr.notFound.home}</Link>
    </ParticipantLayout>
  );
}
