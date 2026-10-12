import type { RouteObject } from "react-router";
import { HomePage } from "./admin/HomePage";
import { NotFoundPage } from "./NotFoundPage";
import { VotePlaceholderPage } from "./vote/VotePlaceholderPage";

// Squelette du bloc 3c : les vraies pages arrivent au bloc 7.
export const routes: RouteObject[] = [
  { path: "/", element: <HomePage /> },
  { path: "/v/:slug", element: <VotePlaceholderPage /> },
  { path: "*", element: <NotFoundPage /> },
];
