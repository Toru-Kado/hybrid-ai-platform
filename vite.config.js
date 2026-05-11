import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "desktop/dist",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./desktop/src/test/setup.js",
    exclude: ["e2e/**", "node_modules/**", ".cache/**", "infra/**"],
  },
});
