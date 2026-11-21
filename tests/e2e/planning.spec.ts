import { readFile } from "node:fs/promises";
import { expect, test, type Locator, type Page } from "@playwright/test";

async function expectNoPageOverflow(page: Page) {
  await expect.poll(() => page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )).toBeLessThanOrEqual(0);
}

async function tabTo(page: Page, target: Locator) {
  for (let step = 0; step < 20; step++) {
    if (await target.evaluate((element) => element === document.activeElement)) {
      break;
    }
    await page.keyboard.press("Tab");
  }
  await expect(target).toBeFocused();
}

test("planner reviews, runs, compares and exports one persisted scenario", async (
  { page },
  testInfo,
) => {
  test.setTimeout(150_000);
  const submitted: string[] = [];
  const externalRequests: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if ((url.protocol === "http:" || url.protocol === "https:") && url.hostname !== "127.0.0.1") {
      externalRequests.push(url.origin);
    }
    if (
      request.method() === "POST" &&
      /\/api\/v1\/scenarios\/[^/]+\/runs$/.test(url.pathname)
    ) {
      submitted.push(request.postDataJSON().kind);
    }
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Bajaur planning overview" })).toBeVisible();
  await expect(page.getByText(/synthetic demonstration/i).first()).toBeVisible();
  await expect(page.getByText("Community clusters", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("overview.png"), fullPage: true });
  await page.getByRole("link", { name: "Data Explorer" }).first().click();
  await expect(page.getByRole("heading", { name: "Explore the Bajaur dataset" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Community demand per modeled week" }).getByRole("row")).toHaveCount(25);
  await page.goBack();
  await page.getByRole("link", { name: /start scenario/i }).click();
  await expect(page.getByRole("heading", { name: "Scenario builder" })).toBeVisible();

  await page.getByRole("button", { name: "Review plan" }).click();
  await expect(page.getByRole("heading", { name: "Review scenario" })).toBeVisible();
  expect(submitted).toEqual([]);
  const confirmed = page.waitForResponse(
    (response) => response.request().method() === "POST" && /\/confirm$/.test(response.url()),
  );
  await page.getByRole("button", { name: "Confirm & Run" }).click();
  const confirmation = await confirmed;
  expect(confirmation.ok()).toBe(true);
  const scenario = await confirmation.json();
  expect(scenario.plan_hash).toMatch(/^[a-f0-9]{64}$/);
  expect(scenario.status).toBe("CONFIRMED");

  await expect(page.getByRole("heading", { name: "Baseline run" })).toBeVisible();
  await expect(page.getByText("Audit passed", { exact: true })).toBeVisible({ timeout: 25_000 });
  const baselineURL = page.url();
  await page.reload();
  await expect(page.getByText("Audit passed", { exact: true })).toBeVisible({ timeout: 25_000 });
  expect(submitted).toEqual(["baseline"]);

  await page.getByRole("button", { name: "Run optimized plan" }).click();
  await expect(page.getByRole("heading", { name: "Optimized run" })).toBeVisible();
  await expect(page.getByText("Audit passed", { exact: true })).toBeVisible({ timeout: 25_000 });
  expect(submitted).toEqual(["baseline", "optimized"]);
  await page.getByRole("link", { name: "Compare results" }).click();
  await expect(page.getByRole("heading", { name: "Compare allocations" })).toBeVisible();
  await expect(page.getByText("Within-threshold coverage", { exact: true }).first()).toBeVisible();
  const zoneRows = page.getByRole("table", { name: "Weekly coverage by zone class" }).locator("tbody tr");
  await expect(zoneRows).toHaveCount(3);
  const zoneTotals = await zoneRows.evaluateAll((rows) => rows.reduce((total, row) => {
    const counts = Array.from(row.querySelectorAll("td"), (cell) =>
      Number.parseInt((cell.textContent ?? "").replaceAll(",", ""), 10));
    return total.map((sum, index) => sum + counts[index]);
  }, [0, 0, 0]));
  expect(zoneTotals).toEqual([2598, 1320, 1853]);
  await page.screenshot({ path: testInfo.outputPath("comparison.png"), fullPage: true });
  const desktopViewport = page.viewportSize()!;
  await page.setViewportSize({ width: 375, height: 812 });
  await expectNoPageOverflow(page);
  await expect(page.getByRole("region", { name: "Community coverage comparison" })).toBeVisible();
  await page.setViewportSize(desktopViewport);

  await page.getByRole("link", { name: "Alternative report" }).click();
  await expect(page.getByRole("heading", { name: "Planning report" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence-linked explanation" })).toBeVisible();
  await expect(page.getByText("Metric evidence paths", { exact: true })).toBeVisible();
  const [jsonDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Download JSON" }).click(),
  ]);
  expect(jsonDownload.suggestedFilename()).toMatch(/\.json$/);
  const report = JSON.parse(await readFile(await jsonDownload.path(), "utf8"));
  expect(report.data_warning).toMatch(/synthetic demonstration/i);
  expect(report.dataset_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(report.plan_hash).toBe(scenario.plan_hash);
  expect(report.dataset.is_synthetic).toBe(true);
  expect(report.dataset.communities).toHaveLength(24);
  expect(report.dataset.sites).toHaveLength(13);
  expect(report.result.solver_status).toBe("OPTIMAL");
  expect(report.result.audit.passed).toBe(true);
  expect(report.result.audit.checks.length).toBeGreaterThan(0);
  expect(report.result.metrics.covered_visits).toBe(1853);
  expect(report.result.metrics.total_demand).toBe(2598);
  const [csvDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Download CSV" }).click(),
  ]);
  expect(csvDownload.suggestedFilename()).toMatch(/\.csv$/);
  const csv = await readFile(await csvDownload.path(), "utf8");
  expect(csv).toContain("section,id,related_id,field,value");
  expect(csv).toContain(report.dataset_sha256);
  expect(csv).toContain("covered_visits,1853");
  await page.screenshot({ path: testInfo.outputPath("report.png"), fullPage: true });

  await page.goBack();
  await expect(page.getByRole("heading", { name: "Compare allocations" })).toBeVisible();
  await page.locator('a[href^="/stress?"]').click();
  await expect(page.getByRole("heading", { name: "Stress Lab" })).toBeVisible();
  await page.getByRole("spinbutton", { name: "Case count" }).fill("3");
  const queued = page.waitForResponse((response) =>
    response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/stress-runs",
  );
  await page.getByRole("button", { name: "Run stress test" }).click();
  const stressResponse = await queued;
  expect(stressResponse.status()).toBe(202);
  const stress = await stressResponse.json();
  await expect(page.getByText("Stress run completed.")).toBeVisible({ timeout: 45_000 });
  await expect(page.getByRole("heading", { name: "Coverage across scenarios" })).toBeVisible();
  const observations = page.getByRole("table", { name: "Stress outcomes by scenario and allocation" });
  await expect(observations.getByRole("row")).toHaveCount(4);
  await expect(observations.getByText(/Audit passed/)).toHaveCount(6);
  await page.screenshot({ path: testInfo.outputPath("stress.png"), fullPage: true });
  await page.reload();
  await expect(observations.getByRole("row")).toHaveCount(4);
  expect(new URL(page.url()).searchParams.get("run")).toBe(stress.stress_run_id);
  await page.setViewportSize({ width: 375, height: 812 });
  await expectNoPageOverflow(page);
  await page.setViewportSize(desktopViewport);
  await page.goto(baselineURL);
  await expect(page.getByText("Audit passed", { exact: true })).toBeVisible();
  expect(submitted).toEqual(["baseline", "optimized"]);
  const history = await page.request.get("/api/v1/runs");
  expect(history.ok()).toBe(true);
  const runs = (await history.json()).filter(
    (run: { scenario_id: string }) => run.scenario_id === scenario.scenario_id,
  );
  expect(runs).toHaveLength(2);
  expect(runs.map((run: { status: string }) => run.status)).toEqual(["COMPLETED", "COMPLETED"]);
  expect(externalRequests).toEqual([]);
});

test("mobile planner is keyboard accessible and scenario controls fit 375px", async (
  { page },
  testInfo,
) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/compare");
  await expect(page.getByRole("heading", { name: "Choose saved runs" })).toBeVisible();
  await page.goto("/scenarios/new");
  await expect(page.getByRole("heading", { name: "Scenario builder" })).toBeVisible();
  await expect(page.getByText(/synthetic demonstration/i).first()).toBeVisible();
  const budget = page.getByRole("spinbutton", { name: "Budget (PKR/week)" });
  await expect(budget).toBeVisible();
  await expect(page.getByRole("button", { name: "Review plan" })).toBeEnabled();
  await expectNoPageOverflow(page);

  await tabTo(page, budget);
  await page.screenshot({ path: testInfo.outputPath("scenario-mobile.png"), fullPage: true });
  await budget.press("ControlOrMeta+A");
  await budget.press("Backspace");
  await budget.press("-");
  await budget.press("1");
  await expect(budget).toHaveValue("-1");
  const review = page.getByRole("button", { name: "Review plan" });
  await tabTo(page, review);
  await page.keyboard.press("Enter");
  await expect(budget).toHaveAttribute("aria-invalid", "true");
  await expect(budget).toBeFocused();
  await budget.press("ControlOrMeta+A");
  await budget.press("Backspace");
  await budget.press("0");
  await expect(budget).toHaveValue("0");
  await tabTo(page, review);
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Review scenario" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm & Run" })).toBeVisible();
  await expectNoPageOverflow(page);
});

test("an infeasible equity floor publishes a diagnostic without an allocation", async ({ page }) => {
  await page.goto("/scenarios/new");
  const review = page.getByRole("button", { name: "Review plan" });
  await expect(review).toBeEnabled();
  await page.getByRole("spinbutton", { name: "Coverage threshold (minutes)" }).fill("1");
  await page.getByRole("spinbutton", { name: "Equity floor (%)" }).fill("100");
  await review.click();
  await expect(page.getByRole("heading", { name: "Review scenario" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm & Run" }).click();
  await expect(page.getByRole("heading", { name: "Baseline run" })).toBeVisible();
  await expect(page.getByText(/baseline is infeasible under the selected policy/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /report/i })).toHaveCount(0);
  const run = new URL(page.url()).pathname;
  const response = await page.request.get("/api/v1" + run);
  expect(response.ok()).toBe(true);
  const snapshot = await response.json();
  expect(snapshot.status).toBe("NO_SOLUTION");
  expect(snapshot.solver_status).toBe("INFEASIBLE");
  expect(snapshot.result).toBeUndefined();
});

test("data explorer validates and publishes a signed synthetic version", async ({ page }) => {
  await page.goto("/data");
  await page.getByText("Import a synthetic dataset", { exact: true }).click();
  const bundle = page.getByLabel("Dataset or JSON-wrapped CSV bundle");
  await bundle.setInputFiles({
    name: "invalid.json", mimeType: "application/json", buffer: Buffer.from("{"),
  });
  await page.getByRole("button", { name: "Publish version" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "valid UTF-8 JSON" })).toBeVisible();
  await bundle.setInputFiles("services/api/tests/fixtures/golden.json");
  await page.getByRole("button", { name: "Publish version" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Published synthetic version" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Community demand per modeled week" })
    .getByRole("row")).toHaveCount(3);
});
