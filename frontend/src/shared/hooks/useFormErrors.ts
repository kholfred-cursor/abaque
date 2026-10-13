import { useCallback, useRef, useState, type RefObject } from "react";
import { ApiError } from "../api/errors";
import { fr } from "../i18n/fr";

type Refs<K extends string> = Record<K, RefObject<HTMLInputElement | null>>;

/**
 * Field errors + one global error, with focus management: the first invalid field (in
 * declaration order) or the global alert receives focus, so keyboard and screen-reader
 * users land on the problem.
 */
export function useFormErrors<K extends string>(order: readonly K[]) {
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<K, string>>>({});
  const [globalError, setGlobalError] = useState<string | null>(null);
  const alertRef = useRef<HTMLDivElement>(null);

  const requireFilled = useCallback(
    (values: Record<K, string>, refs: Refs<K>): boolean => {
      const errors: Partial<Record<K, string>> = {};
      for (const key of order) if (values[key].trim() === "") errors[key] = fr.fields.required;
      setFieldErrors(errors);
      setGlobalError(null);
      const first = order.find((key) => errors[key]);
      if (first) {
        refs[first].current?.focus();
        return false;
      }
      return true;
    },
    [order],
  );

  const showError = useCallback((error: unknown) => {
    const message = error instanceof ApiError ? error.message : fr.errors.NETWORK;
    setGlobalError(message);
    requestAnimationFrame(() => alertRef.current?.focus());
  }, []);

  return { fieldErrors, globalError, alertRef, requireFilled, showError, setGlobalError };
}
