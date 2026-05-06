import { test, expect } from "@playwright/test";

test("homepage loads without errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(err.message));

  await page.goto("/");
  await expect(page).toHaveTitle(/.+/);

  expect(errors).toHaveLength(0);
});
