import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function readJson(relativePath: string) {
  return JSON.parse(readFileSync(new URL(relativePath, import.meta.url), "utf8"));
}

describe("workspace demo artifacts", () => {
  it("can consume the checked-in synthetic dataset and strict plan schema as JSON", () => {
    const dataset = readJson("../../../data/demo/bajaur-v1.json");
    const plan = readJson("../../../data/schemas/plan.schema.json");

    expect(dataset.id).toBe("demo-bajaur-v1");
    expect(dataset.is_synthetic).toBe(true);
    expect(dataset.communities).toHaveLength(24);
    expect(plan.additionalProperties).toBe(false);
    expect(plan.required).toContain("dataset_version_id");
  });
});
