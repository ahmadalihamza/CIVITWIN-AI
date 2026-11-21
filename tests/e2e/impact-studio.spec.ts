import { expect, test } from "@playwright/test";

test("Impact Studio turns a mission into two audited simulations", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/studio");
  await expect(page.getByRole("heading", { name: /Who gets care next/i })).toBeVisible();
  await expect(page.getByText(/recorded synthetic benchmark/i)).toBeVisible();
  await page.getByRole("button", { name: /Demand surge/i }).click();
  await expect(page.getByRole("slider", { name: "Demand level" })).toHaveValue("125");
  await page.getByRole("button", { name: /Reach the overlooked/i }).click();
  await expect(page.getByRole("slider", { name: "Demand level" })).toHaveValue("100");
  await page.getByRole("button", { name: /Run verified simulation/i }).click();
  await expect(page.getByRole("heading", { name: "Here is what changed" })).toBeVisible({ timeout: 80_000 });
  await expect(page.getByText("Both allocations independently audited")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Who gains, and who gives up access/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Open audited comparison/i })).toHaveAttribute("href", /compare\?baseline=.*&alternative=/);
  await page.getByRole("button", { name: "Is it fair?" }).click();
  await expect(page.getByText(/modeled communities gain covered visits/i)).toBeVisible();
  await page.getByRole("button", { name: "Can I trust these numbers?" }).click();
  await expect(page.getByText(/both runs passed their independent allocation audit/i)).toBeVisible();
});

test("Impact Studio responsive mobile layout does not overflow", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/studio");
  await expect(page.getByRole("heading", { name: /Who gets care next/i })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await expect(page.getByRole("button", { name: /Run verified simulation/i })).toBeVisible();
});
