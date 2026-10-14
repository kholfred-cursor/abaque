import { render } from "@testing-library/react";
import { StrictMode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { Providers } from "../App";
import { buildRoutes } from "../routes";
import { createApiClient } from "../shared/api/client";
import type { FakeApi } from "./fakeApi";

/** Render the whole application at ``path`` against a fake API. */
export function renderApp(path: string, api: FakeApi, { strict = false } = {}) {
  const router = createMemoryRouter(buildRoutes(false), { initialEntries: [path] });
  const client = createApiClient({ baseUrl: "http://abaque.test", fetch: api.fetch });
  const tree = (
    <Providers client={client}>
      <RouterProvider router={router} />
    </Providers>
  );
  render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  return router;
}
