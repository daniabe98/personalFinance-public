import axe from "axe-core";

import { expect, login, test } from "./support/fixtures";

async function expectNoAxeViolations(page: import("@playwright/test").Page) {
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(async () => {
    const axeRunner: unknown = Reflect.get(globalThis, "axe");
    if (typeof axeRunner !== "object" || axeRunner === null) {
      throw new Error("Axe did not load");
    }
    const run: unknown = Reflect.get(axeRunner, "run");
    if (typeof run !== "function") throw new Error("Axe runner is unavailable");
    const result: unknown = await Reflect.apply(run, axeRunner, [document]);
    if (typeof result !== "object" || result === null) {
      throw new Error("Axe returned an invalid result");
    }
    const rawViolations: unknown = Reflect.get(result, "violations");
    if (!Array.isArray(rawViolations)) {
      throw new Error("Axe returned invalid violations");
    }
    return rawViolations.map((violation: unknown) => {
      if (typeof violation !== "object" || violation === null) {
        throw new Error("Axe returned an invalid violation");
      }
      return {
        id: String(Reflect.get(violation, "id")),
        help: String(Reflect.get(violation, "help")),
      };
    });
  });
  expect(violations).toEqual([]);
}

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
  await expectNoAxeViolations(page);

  await page.getByRole("link", { name: "Organizar" }).click();
  const accountsTab = page.getByRole("tab", { name: "Cuentas" });
  const categoriesTab = page.getByRole("tab", { name: "Categorías" });
  await accountsTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(categoriesTab).toBeFocused();
  await expect(categoriesTab).toHaveAttribute("aria-selected", "true");
  await expectNoAxeViolations(page);

  await page.getByRole("link", { name: "Ajustes" }).click();
  await expect(
    page.getByRole("heading", { name: "Copias de seguridad" }),
  ).toBeVisible();
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    await expectNoAxeViolations(page);
  }
});
