import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: "list",
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: [
    {
      command: "EVIDENCEAI_E2E=1 ../api/.venv/bin/python e2e/server.py",
      url: "http://127.0.0.1:18000/api/v1/health",
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 15000 },
      timeout: 30000,
    },
    {
      command:
        "NEXT_PUBLIC_API_BASE_URL=http://localhost:18000 npm run build && NEXT_PUBLIC_API_BASE_URL=http://localhost:18000 npm run start -- --hostname 127.0.0.1 --port 3100",
      url: "http://localhost:3100/login",
      reuseExistingServer: false,
      gracefulShutdown: { signal: "SIGTERM", timeout: 15000 },
      timeout: 60000,
    },
  ],
});
