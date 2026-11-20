import { randomUUID } from "node:crypto";
import { resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";

const apiPort = 18200;
const webPort = 13200;
const apiURL = "http://127.0.0.1:" + apiPort;
const webURL = "http://127.0.0.1:" + webPort;
const databasePath = resolve("test-results", "browser-db", randomUUID() + ".db");

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "test-results/browser-artifacts",
  timeout: 90_000,
  expect: { timeout: 12_000 },
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  use: {
    baseURL: webURL,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "uv run --locked --no-sync uvicorn app.main:app --app-dir services/api "
        + "--host 127.0.0.1 --port " + apiPort,
      url: apiURL + "/api/v1/ready",
      timeout: 90_000,
      reuseExistingServer: false,
      env: {
        DATABASE_URL: "sqlite:///" + databasePath.replaceAll("\\", "/"),
        DEMO_MODE: "true",
        AI_ENABLED: "false",
        LLM_API_KEY: "",
        LLM_MODEL: "",
        WEB_ORIGIN: webURL,
      },
    },
    {
      command: "npm run dev --workspace @civitwin/web -- --port " + webPort,
      url: webURL,
      timeout: 240_000,
      reuseExistingServer: false,
      env: {
        API_INTERNAL_URL: apiURL,
        NEXT_DIST_DIR: ".next-e2e",
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
