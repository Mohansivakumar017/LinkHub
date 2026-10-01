import { test, expect } from "@playwright/test";

test("frontend and proxied API are reachable", async ({ page, request }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/LinkHub/i);
  await expect(page.locator("body")).toContainText(/LinkHub/i);

  const health = await request.get("/api/v1/health");
  expect(health.ok()).toBeTruthy();
  expect(await health.json()).toMatchObject({ status: "ok" });
});

test("shared-link entry route renders the access screen", async ({ page }) => {
  await page.goto("/?link=acceptance-test");
  await expect(page.getByRole("heading", { name: "Open shared link" })).toBeVisible();
  await expect(page.getByText("acceptance-test")).toBeVisible();
});
