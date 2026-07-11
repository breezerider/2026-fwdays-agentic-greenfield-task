import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the F1 @web slice.
 *
 * Architecture (Pitfall G + D-05 discretion):
 *   Single-origin webServer: the test origin is the uvicorn process
 *   serving the API at `/api/v1/*` AND the static `frontend/out/`
 *   export mounted at `/` (StaticFiles, env-gated by
 *   `EPUBTV_SERVE_STATIC=true EPUBTV_FRONTEND_OUT=…`). This eliminates
 *   CORS quirks during the e2e flow — both the SPA's `fetch` to the
 *   API and the page navigation are on the same origin.
 *
 * Sequence per test run:
 *   1. `globalSetup` runs `yarn build` once to refresh `frontend/out/`
 *      (cheap on Turbopack; ~3-7s).
 *   2. `webServer` boots `uvicorn epubtv.main:app` with the static
 *      env on. `reuseExistingServer: true` lets a local `make demo`
 *      runner use the same instance.
 *   3. Each test starts the static `chromium` project with headless
 *      video off (kept on the test-results dir so the final demo
 *      video can be re-recorded via `document-bdd-feature` skill).
 */
export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts$/,
  // 30s per test — the F1 @smoke contract requires <3s end-to-end,
  // so 30s leaves generous room for spinner + network.
  timeout: 30_000,
  expect: { timeout: 5_000 },

  // Fully parallel: each test gets its own browser context. The
  // single-uvicorn process handles them serially at the FastAPI level
  // which is fine for F1 (one POST at a time).
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // Single worker — the backend is a single uvicorn process; the
  // F2/F5 e2e tests do longer flows (upload + chooser + config + WS)
  // that race the same backend SQLite WAL when run in parallel. v2
  // can re-enable parallelism with a per-test DB.
  workers: 1,

  reporter: process.env.CI
    ? [["list"], ["html", { open: "never" }]]
    : [["list"]],

  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
    // 1280x720 — 16:9 HD per D-05; matches the corrected
    // `document-bdd-feature` recording config (which mandates
    // 1280x720 per D-03); avoids the scaling artifacts that
    // produced pixelation in the Phase 2 video.
    viewport: { width: 1280, height: 720 },
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  globalSetup: require.resolve("./tests/global-setup.ts"),

  webServer: {
    command:
      "cd ../backend && EPUBTV_SERVE_STATIC=true " +
      "EPUBTV_FRONTEND_OUT=../frontend/out " +
      "EPUBTV_DB_PATH=./db/test.db " +
      "EPUBTV_SCRATCH_DIR=./scratch/test " +
      "uv run uvicorn epubtv.main:app --port 5173 --host 127.0.0.1 --workers 1",
    port: 5173,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
