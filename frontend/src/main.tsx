import "@fontsource-variable/atkinson-hyperlegible-next";
import "./shared/design/tokens.css";
import "./index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { Providers } from "./App";
import { router } from "./router";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("Élément #root introuvable");
}

createRoot(container).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
);
