import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === "web" ? "/" : "./",
  define: mode === "web" ? { global: "globalThis" } : {},
  build: {
    outDir: mode === "web" ? "dist/web" : "desktop/dist",
    emptyOutDir: true,
  },
  server: {
    proxy: mode === "web"
      ? { "/api": "https://d1c6xbr99w8fr2.cloudfront.net" }
      : undefined,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./desktop/src/test/setup.js",
    exclude: ["e2e/**", "node_modules/**", ".cache/**", "infra/**"],
  },
}));
