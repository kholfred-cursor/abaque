import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Dev server: /api and /health are proxied to the API container (same origin as in production).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: "http://api:8000", changeOrigin: false },
      "/health": { target: "http://api:8000", changeOrigin: false },
    },
  },
  build: {
    sourcemap: false,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
