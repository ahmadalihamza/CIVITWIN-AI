import { expect, test } from "@playwright/test";

test("Impact Studio turns a mission into two audited simulations", async ({ page }, testInfo) => {
  test.setTimeout(120_000);
  const submissions: string[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && path.startsWith("/api/v1/scenarios")) submissions.push(path);
  });
  await page.goto("/");
  await page.getByRole("navigation").getByRole("link", { name: "Impact Studio" }).click();
  await expect(page.getByRole("heading", { name: /Who gets care next/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Simulation results" })).toBeVisible();
  await page.getByRole("button", { name: /Demand surge/i }).click();
  const demand = page.getByRole("slider", { name: "Demand level" });
  await expect(demand).toHaveValue("125");
  await demand.press("ArrowRight");
  await expect(demand).toHaveValue("130");
  await page.getByRole("button", { name: /Tough budget choice/i }).click();
  await expect(page.getByRole("slider", { name: "Weekly budget" })).toHaveValue("150000");
  await expect(page.getByRole("slider", { name: "New mobile service units" })).toHaveValue("1");
  await page.getByRole("button", { name: /Reach the overlooked/i }).click();
  await expect(demand).toHaveValue("100");
  const review = page.getByRole("button", { name: "Review simulation plan" });
  await review.click();
  await expect(page.getByRole("heading", { name: "Review the plan for one modeled week" })).toBeVisible();
  expect(submissions).toEqual([]);
  await demand.press("ArrowRight");
  await expect(review).toBeVisible();
  await demand.press("ArrowLeft");
  await review.click();
  await page.getByRole("button", { name: "Confirm and run both allocations" }).click();
  await expect(page.getByRole("heading", { name: "Here is what changed" })).toBeVisible({ timeout: 80_000 });
  await expect(page.getByText("Both allocations independently audited")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Who gains, and who gives up access/i })).toBeVisible();
  const comparison = page.getByRole("link", { name: "Open audited comparison" });
  const pair = new URL((await comparison.getAttribute("href"))!, page.url()).searchParams;
  const response = await page.request.post("/api/v1/comparisons", { data: {
    baseline_run_id: pair.get("baseline"), alternative_run_id: pair.get("alternative"),
  } });
  expect(response.ok()).toBe(true);
  const { baseline, alternative } = await response.json();
  expect(baseline.audit.passed && alternative.audit.passed).toBe(true);
  expect(submissions.map((path) => path.split("/").at(-1))).toEqual(["scenarios", "confirm", "runs", "runs"]);
  const before = baseline.metrics.clusters.find((row: { community_id: string }) => row.community_id === "C01");
  const after = alternative.metrics.clusters.find((row: { community_id: string }) => row.community_id === "C01");
  const network = page.getByRole("region", { name: "Synthetic service network" });
  const coverage = network.getByLabel("Coverage view");
  await expect(network.getByRole("button", { name: /Selected site/ })).toHaveCount(alternative.selected_candidate_ids.length);
  await coverage.selectOption("baseline");
  await expect(network.getByRole("button", { name: /Selected site/ })).toHaveCount(0);
  await coverage.selectOption("optimized");
  await network.getByRole("button", { name: /Community 01 · Existing sites/ }).press("Enter");
  await expect(network.getByText("Covered visits/week " + before.covered_visits + " → " + after.covered_visits, { exact: false })).toBeVisible();
  await coverage.selectOption("change");
  await page.getByRole("button", { name: "Is it fair?" }).click();
  await expect(page.getByText(/modeled communities gain covered visits/i)).toBeVisible();
  await page.getByRole("button", { name: "Can I trust these numbers?" }).click();
  await expect(page.getByText(/both runs passed their independent allocation audit/i)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("studio-audited.png"), fullPage: true });
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(375);
  await page.getByRole("link", { name: "Full evidence report" }).click();
  await expect(page.getByRole("heading", { name: "Planning report" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Download JSON" })).toBeVisible();
});

test("Impact Studio responsive mobile layout does not overflow", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/studio");
  await expect(page.getByRole("heading", { name: /Who gets care next/i })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await expect(page.getByRole("button", { name: "Review simulation plan" })).toBeVisible();
});

test("Impact Studio keeps an infeasible baseline inspectable without showing metrics", async ({ page }) => {
  await page.goto("/studio");
  const threshold = page.getByRole("slider", { name: "Travel-time threshold" });
  await threshold.press("Home");
  await page.getByText("Advanced: protect every community").click();
  await page.getByRole("slider", { name: "Minimum coverage floor" }).press("End");
  await page.getByRole("button", { name: "Review simulation plan" }).click();
  await page.getByRole("button", { name: "Confirm and run both allocations" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /baseline is infeasible/i })).toBeVisible({ timeout: 25_000 });
  await expect(page.getByRole("link", { name: "Baseline run" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Simulation results" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Full evidence report" })).toHaveCount(0);
});
