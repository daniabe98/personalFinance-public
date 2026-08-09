import { expect, login, test } from "./support/fixtures";

test("preserves landmarks, visible focus and the mobile reading order", async ({
  page,
  runtime,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await login(page, runtime);
  await expect(page.getByRole("main")).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Navegación principal" }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(375);
});
