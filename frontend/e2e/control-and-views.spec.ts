import type { Locator, Page } from "@playwright/test";

import { expect, login, test } from "./support/fixtures";

interface SeededScenario {
  readonly accountName: string;
  readonly incomeDescription: string;
}

async function seedScenario(page: Page): Promise<SeededScenario> {
  return await page.evaluate(async () => {
    const accountName = "Cuenta control E2E";
    const incomeDescription = "Ingreso reversible E2E";
    const session = await fetch("/api/v1/auth/session", {
      credentials: "include",
    });
    if (!session.ok) throw new Error("E2E session setup failed");
    const { csrf_token: csrfToken } = (await session.json()) as {
      csrf_token: string;
    };
    let sequence = 0;
    async function post<T>(
      path: string,
      body: Readonly<Record<string, unknown>>,
      idempotent = false,
    ): Promise<T> {
      sequence += 1;
      const response = await fetch(path, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
          ...(idempotent
            ? { "Idempotency-Key": `control-e2e-${sequence}` }
            : {}),
        },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        throw new Error(`E2E seed failed: ${path} (${response.status})`);
      }
      return (await response.json()) as T;
    }
    const account = await post<{ id: string }>("/api/v1/accounts", {
      name: accountName,
      kind: "ASSET",
      is_reconcilable: true,
    });
    const category = await post<{ id: string }>("/api/v1/categories", {
      name: "Ingresos control E2E",
      kind: "INCOME",
    });
    await post(
      "/api/v1/transactions/opening",
      {
        account_id: account.id,
        amount_cents: 100_000,
        economic_date: "2025-01-01",
        description: "Base conciliable E2E",
      },
      true,
    );
    await post(
      "/api/v1/transactions/income",
      {
        account_id: account.id,
        category_id: category.id,
        amount_cents: 20_000,
        economic_date: "2025-01-10",
        cash_date: "2025-01-10",
        description: incomeDescription,
      },
      true,
    );
    return { accountName, incomeDescription };
  });
}

function reportSection(page: Page, heading: string): Locator {
  return page.getByRole("heading", { name: heading }).locator("..");
}

async function loadReport(
  page: Page,
  start: string,
  end: string,
): Promise<void> {
  await page.getByLabel("Desde").fill(start);
  await page.getByLabel("Hasta").fill(end);
  await page.getByRole("button", { name: "Actualizar" }).click();
  await expect(
    page.getByRole("heading", { name: "Actividad del periodo" }),
  ).toBeVisible();
}

async function expectActivityReflow(
  page: Page,
  economic: Locator,
  width: number,
  expectedSummaryColumns: number,
): Promise<void> {
  await page.setViewportSize({ width, height: 900 });

  const summary = economic.locator(".activity-totals");
  await expect(summary).toHaveCSS("display", "grid");
  expect(
    await summary.evaluate(
      (element) =>
        getComputedStyle(element).gridTemplateColumns.split(" ").filter(Boolean)
          .length,
    ),
  ).toBe(expectedSummaryColumns);

  const detailTargets = await economic
    .getByRole("link", { name: /^Ver detalle de Movimiento,/ })
    .evaluateAll((links) =>
      links.map((link) => {
        const bounds = link.getBoundingClientRect();
        return { width: bounds.width, height: bounds.height };
      }),
    );
  expect(detailTargets).toHaveLength(2);
  for (const target of detailTargets) {
    expect(target.width).toBeGreaterThanOrEqual(48);
    expect(target.height).toBeGreaterThanOrEqual(48);
  }

  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
  const clippedContent = await economic.evaluate((surface) => {
    const elements = [surface, ...surface.querySelectorAll("*")];
    return elements.flatMap((element, index) => {
      if (!(element instanceof HTMLElement)) return [];
      const style = getComputedStyle(element);
      const clipsHorizontal = ["hidden", "clip"].includes(style.overflowX);
      const clipsVertical = ["hidden", "clip"].includes(style.overflowY);
      const truncatesHorizontal =
        element.scrollWidth > element.clientWidth + 1 &&
        (clipsHorizontal ||
          style.whiteSpace === "nowrap" ||
          style.textOverflow === "ellipsis");
      const truncatesVertical =
        element.scrollHeight > element.clientHeight + 1 && clipsVertical;
      return truncatesHorizontal || truncatesVertical ? [index] : [];
    });
  });
  expect(clippedContent).toEqual([]);
}

test("reverses, reconciles and reports exact cross-period effects on the real ledger", async ({
  page,
  runtime,
}) => {
  await login(page, runtime);
  const scenario = await seedScenario(page);

  await page.reload();
  await expect(
    page.getByRole("navigation", { name: "Navegación principal" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Movimientos" }).click();
  const original = page
    .getByRole("listitem")
    .filter({ hasText: scenario.incomeDescription });
  await expect(original).toContainText("Contabilizado");
  await original
    .getByRole("button", { name: "Anular con un movimiento compensatorio" })
    .click();
  const dialog = page.locator("dialog").filter({
    has: page.getByRole("heading", {
      name: "Anular con un movimiento compensatorio",
    }),
  });
  await dialog.getByLabel("Fecha del cambio").fill("2025-02-05");
  await dialog.getByLabel("Fecha en la cuenta").fill("2025-02-05");
  await dialog.getByRole("button", { name: "Confirmar compensación" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(original).toContainText("Movimiento compensatorio");
  const reversal = page
    .getByRole("listitem")
    .filter({
      has: page.locator("strong").filter({
        hasText: /^Movimiento compensatorio$/,
      }),
    })
    .filter({ hasText: "2025-02-05" });
  await expect(reversal).toContainText("Movimiento original");

  await page.getByRole("link", { name: "Resumen", exact: true }).click();
  const economic = reportSection(page, "Actividad del periodo");
  const cash = reportSection(page, "Dinero disponible");
  const worth = reportSection(page, "Patrimonio");

  await loadReport(page, "2025-01-01", "2025-01-31");
  await expect(economic).toContainText(/Ingresos\s*200,00 €/);
  await expect(economic).toContainText(/Resultado\s*200,00 €/);
  await expect(cash).toContainText(/Cobros\s*200,00 €/);
  await expect(worth).toContainText(/Activos\s*1\.200,00 €/);

  await loadReport(page, "2025-02-01", "2025-02-28");
  await expect(economic).toContainText(/Ingresos\s*-200,00 €/);
  await expect(economic).toContainText(/Resultado\s*-200,00 €/);
  await expect(cash).toContainText(/Cobros\s*-200,00 €/);
  await expect(worth).toContainText(/Activos\s*1\.000,00 €/);

  await loadReport(page, "2025-01-01", "2025-02-28");
  await expect(economic).toContainText(/Ingresos\s*0,00 €/);
  await expect(economic).toContainText(/Gastos\s*0,00 €/);
  await expect(cash).toContainText(/Cambio neto\s*0,00 €/);
  await expect(worth).toContainText(/Activos\s*1\.000,00 €/);

  const activity = economic.getByRole("list");
  const movements = activity.getByRole("listitem");
  await expect(movements).toHaveCount(2);
  const januaryMovement = movements.nth(0);
  const februaryMovement = movements.nth(1);

  await expect(
    januaryMovement.locator('time[datetime="2025-01-10"]'),
  ).toHaveText("10 ene 2025");
  await expect(
    februaryMovement.locator('time[datetime="2025-02-05"]'),
  ).toHaveText("5 feb 2025");
  await expect(
    januaryMovement.getByText("Movimiento", { exact: true }),
  ).toBeVisible();
  await expect(
    februaryMovement.getByText("Movimiento", { exact: true }),
  ).toBeVisible();
  await expect(
    januaryMovement.getByText("+200,00 €", { exact: true }),
  ).toBeVisible();
  await expect(
    februaryMovement.getByText("−200,00 €", { exact: true }),
  ).toBeVisible();

  const januaryDetail = januaryMovement.getByRole("link", {
    name: "Ver detalle de Movimiento, +200,00 €, 10 ene 2025, 1 de 2",
  });
  const februaryDetail = februaryMovement.getByRole("link", {
    name: "Ver detalle de Movimiento, −200,00 €, 5 feb 2025, 2 de 2",
  });
  await expect(januaryDetail).toHaveText("Ver detalle");
  await expect(februaryDetail).toHaveText("Ver detalle");
  await expect(activity).not.toContainText(
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
  );

  await expectActivityReflow(page, economic, 375, 1);
  await expectActivityReflow(page, economic, 768, 3);
  await expectActivityReflow(page, economic, 1024, 3);
  await expectActivityReflow(page, economic, 1440, 3);

  const focusableElements = page.locator(
    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  );
  let reachedJanuaryDetailWithKeyboard = false;
  const tabLimit = (await focusableElements.count()) + 1;
  for (let tabIndex = 0; tabIndex < tabLimit; tabIndex += 1) {
    await page.keyboard.press("Tab");
    if (
      await januaryDetail.evaluate(
        (link) => link.ownerDocument.activeElement === link,
      )
    ) {
      reachedJanuaryDetailWithKeyboard = true;
      break;
    }
  }
  expect(reachedJanuaryDetailWithKeyboard).toBe(true);
  await expect(januaryDetail).toBeFocused();
  expect(
    await januaryDetail.evaluate((link) => {
      const style = getComputedStyle(link);
      return (
        link.matches(":focus-visible") &&
        style.outlineStyle !== "none" &&
        Number.parseFloat(style.outlineWidth) > 0
      );
    }),
  ).toBe(true);

  await page.getByRole("link", { name: "Conciliar" }).click();
  await page.getByLabel("Cuenta").selectOption({ label: scenario.accountName });
  await page.getByLabel("Fecha de corte").fill("2025-02-28");
  await page.getByLabel("Saldo real").fill("1.000,00");
  await page.getByRole("button", { name: "Revisar movimientos" }).click();
  const pending = page.getByRole("list", { name: "Movimientos pendientes" });
  await expect(pending.getByRole("checkbox")).toHaveCount(3);
  await expect(pending).toContainText("2025-01-01");
  await expect(pending).toContainText("2025-01-10");
  await expect(pending).toContainText("2025-02-05");
  await expect(pending).toContainText("1.000,00 €");
  await expect(pending).toContainText("200,00 €");
  await expect(pending).toContainText("-200,00 €");
  for (let index = 0; index < 3; index += 1) {
    const preview = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith("/api/v1/reconciliations/preview"),
    );
    await pending.getByRole("checkbox").nth(index).check();
    await preview;
  }
  await expect(page.getByText("La diferencia es cero.")).toBeVisible();
  await page.getByRole("button", { name: "Completar conciliación" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Conciliación completada",
  );

  await page.getByRole("link", { name: "Ajustes" }).click();
  const audit = reportSection(page, "Actividad de seguridad");
  await expect(audit).toContainText("Se contabilizó un movimiento.");
  await expect(audit).toContainText("Resultado: Correcto");
  await expect(page.getByRole("button", { name: /restaur/i })).toHaveCount(0);
});
