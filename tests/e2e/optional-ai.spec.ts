import { expect, test } from "@playwright/test";

test("optional AI drafts require apply and review, with a manual fallback", async ({ page }) => {
  const writes: string[] = [];
  const prompts: unknown[] = [];
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (request.method() === "POST" && pathname.startsWith("/api/v1/scenarios")) {
      writes.push(pathname);
    }
  });
  await page.route("**/api/v1/ready", (route) => route.fulfill({
    json: { status: "ready", ai_enabled: true },
  }));
  await page.route("**/api/v1/plans/parse", (route) => {
    prompts.push(route.request().postDataJSON());
    if (prompts.length === 1) {
      return route.fulfill({ json: {
        status: "manual", draft: null, warnings: ["The parser could not read the prompt."],
        defaults_applied: [],
      } });
    }
    return route.fulfill({ json: {
      status: "draft",
      draft: {
        dataset_version_id: "demo-bajaur-v1", budget_pkr: 150_000, max_new_units: 1,
        threshold_minutes: 45, demand_multiplier_pct: 100, equity_min_pct: 0,
        policy: "coverage_first", seed: 2026,
      },
      defaults_applied: ["threshold_minutes", "demand_multiplier_pct", "equity_min_pct", "seed"],
      warnings: [],
    } });
  });

  await page.goto("/scenarios/new");
  const prompt = page.getByLabel("Planning prompt");
  const budget = page.getByLabel("Budget (PKR/week)", { exact: true });
  await prompt.fill("A suitable investment for our scenario");
  await page.getByRole("button", { name: "Suggest plan" }).click();
  await expect(page.getByText("Manual planning available", { exact: true })).toBeVisible();
  await expect(budget).toHaveValue("300000");

  const text = "Plan with a weekly budget of PKR 150,000 and at most 1 new unit";
  await prompt.fill(text);
  await page.getByRole("button", { name: "Suggest plan" }).click();
  await expect(page.getByRole("heading", { name: "Suggested assumptions" })).toBeVisible();
  await expect(page.getByText(/Defaults used.*Coverage threshold/)).toBeVisible();
  expect(prompts[1]).toEqual({ dataset_version_id: "demo-bajaur-v1", text, language: "en" });
  await expect(budget).toHaveValue("300000");
  expect(writes).toEqual([]);

  await page.getByRole("button", { name: "Apply suggestion" }).click();
  await expect(budget).toHaveValue("150000");
  expect(writes).toEqual([]);
  await page.getByRole("button", { name: "Review plan" }).click();
  await expect(page.getByRole("heading", { name: "Review scenario" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm & Run" })).toBeVisible();
  expect(writes).toEqual(["/api/v1/scenarios"]);
});
