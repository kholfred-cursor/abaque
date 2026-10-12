import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Client typé à partir du schéma OpenAPI généré (npm run gen:api).
// Les middlewares CSRF et de rafraîchissement arrivent au bloc 7.
export const api = createClient<paths>({ baseUrl: "/", credentials: "include" });
