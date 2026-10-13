import { useEffect } from "react";
import { fr } from "../i18n/fr";

export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} | ${fr.app.name}`;
  }, [title]);
}
