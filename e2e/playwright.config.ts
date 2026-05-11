import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const PROJECT_ROOT = path.resolve(__dirname, "..");
const PYTHON_BIN = path.join(PROJECT_ROOT, ".venv", "bin", "python");
const FAKE_SERVER_SCRIPT = path.join(
  PROJECT_ROOT,
  "e2e",
  "helpers",
  "fake_server.py"
);

// Fixed port for integration tests — avoids dynamic port coordination
// between the Python server and Vite's VITE_API_PORT env var.
const TEST_API_PORT = 8766;

export default defineConfig({
  testDir: ".",
  timeout: 30000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  outputDir: "test-results",

  projects: [
    {
      name: "integration",
      testDir: "./integration",
      use: {
        ...devices["Desktop Chrome"],
        baseURL: "http://127.0.0.1:5174",
      },
    },
    {
      name: "electron",
      testDir: "./electron",
      use: {},
    },
  ],

  // Start both the fake Python server and Vite dev server for integration tests.
  webServer: [
    {
      command: `${PYTHON_BIN} ${FAKE_SERVER_SCRIPT} --port ${TEST_API_PORT}`,
      port: TEST_API_PORT,
      cwd: PROJECT_ROOT,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `VITE_API_PORT=${TEST_API_PORT} npx vite --host 127.0.0.1 --port 5174`,
      port: 5174,
      cwd: PROJECT_ROOT,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
