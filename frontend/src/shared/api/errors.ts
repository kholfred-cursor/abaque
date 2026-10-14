import { fr, type ErrorCode } from "../i18n/fr";

/** An API error in the backend's single format: {"error": {"code", "message"}}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, serverMessage?: string) {
    super(
      serverMessage !== undefined && SERVER_MESSAGE_CODES.has(code)
        ? serverMessage
        : messageFor(code),
    );
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Codes whose server message carries a useful detail (a CSV line number, the k threshold).
 * The backend writes these messages in French for display; every other code uses fr.ts. */
const SERVER_MESSAGE_CODES = new Set(["CSV_INVALID", "BELOW_THRESHOLD"]);

/** Known codes get a French message from fr.ts; anything else gets a generic message
 * (server messages are never displayed raw). */
export function messageFor(code: string): string {
  return code in fr.errors ? fr.errors[code as ErrorCode] : fr.errors.GENERIC;
}

function serverMessageOf(body: unknown): string | undefined {
  if (typeof body !== "object" || body === null || !("error" in body)) return undefined;
  const error = body.error;
  if (typeof error !== "object" || error === null || !("message" in error)) return undefined;
  return typeof error.message === "string" ? error.message : undefined;
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
  return new ApiError(status, code, serverMessageOf(body));
}
