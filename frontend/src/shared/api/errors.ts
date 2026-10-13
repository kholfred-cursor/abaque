import { fr, type ErrorCode } from "../i18n/fr";

/** An API error in the backend's single format: {"error": {"code", "message"}}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string) {
    super(messageFor(code));
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Known codes get a French message from fr.ts; anything else gets a generic message
 * (server messages are never displayed raw). */
export function messageFor(code: string): string {
  return code in fr.errors ? fr.errors[code as ErrorCode] : fr.errors.GENERIC;
}

export function toApiError(status: number, body: unknown): ApiError {
  const code =
    typeof body === "object" &&
    body !== null &&
    "error" in body &&
    typeof body.error === "object" &&
    body.error !== null &&
    "code" in body.error &&
    typeof body.error.code === "string"
      ? body.error.code
      : "GENERIC";
  return new ApiError(status, code);
}
