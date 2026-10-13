import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Dev server: /api and /health are proxied to the API container (same origin as in production).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Tests cross-check two reference files outside frontend/ (scale.json, COLOR_KEYS).
    fs: { allow: [".", "../docs/design"] },
    proxy: {
      "/api": { target: "http://api:8000", changeOrigin: false },
      "/health": { target: "http://api:8000", changeOrigin: false },
    },
  },
  build: {
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test/setup.ts"],
    // Process CSS so `?raw` imports return the real file (design mirror tests).
    css: true,
  },
});
