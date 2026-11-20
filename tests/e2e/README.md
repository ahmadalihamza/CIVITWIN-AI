# Browser acceptance tests

Run from the repository root after dependency setup.

```sh
uv sync --locked
npm ci
npx playwright install chromium
npm run e2e
```

Playwright starts the web and API services on localhost ports 13200 and 18200. The API seeds a new SQLite database in `test-results/browser-db/` for each invocation. Traces and downloads use the separate `test-results/browser-artifacts/` folder.

If Chromium was installed with `PLAYWRIGHT_BROWSERS_PATH`, keep that environment setting when running the tests.
