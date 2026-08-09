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
