import type { Page, Request } from "@playwright/test";

import { expect, login, test } from "./support/fixtures";

const DATES = {
  opening: "2026-08-01",
  income: "2026-08-05",
  expense: "2026-08-10",
  transfer: "2026-08-15",
} as const;

async function createAccount(
  page: Page,
  name: string,
  type: "Dinero y bienes" | "Deudas" = "Dinero y bienes",
): Promise<void> {
  const form = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Nueva cuenta" }),
  });
  await form.getByLabel("Nombre").fill(name);
  await form.getByLabel("Tipo").selectOption({ label: type });
  await form.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(
    page.getByRole("listitem").filter({ hasText: name }),
  ).toBeVisible();
}

async function createCategory(
  page: Page,
  name: string,
  use: "Ingresos" | "Gastos",
): Promise<void> {
  const form = page.locator("form").filter({
    has: page.getByRole("heading", { name: "Nueva categoría" }),
  });
  await form.getByLabel("Nombre").fill(name);
  await form.getByLabel("Uso").selectOption({ label: use });
  await form.getByRole("button", { name: "Crear categoría" }).click();
  await expect(
    page.getByRole("listitem").filter({ hasText: name }),
  ).toBeVisible();
}

interface Movement {
  readonly action:
    | "Indicar saldo inicial"
    | "Añadir ingreso"
    | "Añadir gasto"
    | "Mover dinero";
  readonly amount: string;
  readonly account: string;
  readonly date: string;
  readonly description: string;
  readonly category?: string;
  readonly destination?: string;
}

async function prepareMovement(page: Page, movement: Movement): Promise<void> {
  await page.getByLabel(movement.action).check();
  await page.getByLabel("Cantidad en euros").fill(movement.amount);
  await page
    .getByLabel(
      movement.action === "Mover dinero" ? "Cuenta de origen" : "Cuenta",
      { exact: true },
    )
    .selectOption({ label: movement.account });
  if (movement.category !== undefined) {
    await page
      .getByLabel("Categoría")
      .selectOption({ label: movement.category });
  }
  if (movement.destination !== undefined) {
    await page
      .getByLabel("Cuenta de destino")
      .selectOption({ label: movement.destination });
  }
  await page.getByLabel("Fecha del movimiento").fill(movement.date);
  await page.getByLabel("Descripción").fill(movement.description);
  await page.getByRole("button", { name: "Revisar movimiento" }).click();
  await expect(
    page.getByRole("heading", { name: "Revisa antes de guardar" }),
  ).toBeVisible();
}

async function postMovement(page: Page, movement: Movement): Promise<void> {
  await prepareMovement(page, movement);
  await page.getByRole("button", { name: "Contabilizar" }).click();
  await expect(
    page.getByRole("listitem").filter({ hasText: movement.description }),
  ).toBeVisible();
}

async function replayRequest(page: Page, request: Request): Promise<unknown> {
  const headers = request.headers();
  return await page.evaluate(
    async ({ url, body, csrf, idempotencyKey }) => {
      const response = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrf,
          "Idempotency-Key": idempotencyKey,
        },
        body,
      });
      return { status: response.status, payload: await response.json() };
    },
    {
      url: request.url(),
      body: request.postData() ?? "",
      csrf: headers["x-csrf-token"] ?? "",
      idempotencyKey: headers["idempotency-key"] ?? "",
    },
  );
}

test("executes catalog and core financial commands against the packaged HTTPS application", async ({
  page,
  runtime,
}) => {
  await login(page, runtime);
  await page.getByRole("link", { name: "Organizar" }).click();

  await createAccount(page, "Cuenta diaria E2E");
  await createAccount(page, "Ahorro E2E");
  await createAccount(page, "Tarjeta E2E", "Deudas");
  await createCategory(page, "Nómina E2E", "Ingresos");
  await createCategory(page, "Comida E2E", "Gastos");

  const dailyAccount = page
    .getByRole("listitem")
    .filter({ hasText: "Cuenta diaria E2E" });
  await expect(dailyAccount).toContainText("Se comprueba con extractos");
  await expect(
    page.getByRole("listitem").filter({ hasText: "Tarjeta E2E" }),
  ).toContainText("Deudas");

  await page.getByRole("link", { name: "Movimientos" }).click();
  await expect(page.getByLabel("Descripción")).toHaveAttribute("required", "");
  await expect(page.getByLabel("Descripción")).toHaveAttribute(
    "maxlength",
    "500",
  );
  await postMovement(page, {
    action: "Indicar saldo inicial",
    amount: "1.000,00",
    account: "Cuenta diaria E2E",
    date: DATES.opening,
    description: "Saldo inicial E2E",
  });
  await postMovement(page, {
    action: "Añadir ingreso",
    amount: "250,00",
    account: "Cuenta diaria E2E",
    category: "Nómina E2E",
    date: DATES.income,
    description: "Ingreso E2E",
  });
  await postMovement(page, {
    action: "Añadir gasto",
    amount: "50,00",
    account: "Cuenta diaria E2E",
    category: "Comida E2E",
    date: DATES.expense,
    description: "Gasto E2E",
  });

  const transferRequest = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/transactions/transfer"),
  );
  await prepareMovement(page, {
    action: "Mover dinero",
    amount: "100,00",
    account: "Cuenta diaria E2E",
    destination: "Ahorro E2E",
    date: DATES.transfer,
    description: "  Transferencia E2E  ",
  });
  await page.getByRole("button", { name: "Contabilizar" }).click();
  const capturedTransfer = await transferRequest;
  expect(capturedTransfer.postDataJSON()).toMatchObject({
    description: "Transferencia E2E",
  });
  await expect(
    page.getByRole("listitem").filter({ hasText: "Transferencia E2E" }),
  ).toHaveCount(1);

  await expect(replayRequest(page, capturedTransfer)).resolves.toMatchObject({
    status: 200,
    payload: { replayed: true },
  });
  await expect(
    page.getByRole("listitem").filter({ hasText: "Transferencia E2E" }),
  ).toHaveCount(1);

  await page.getByRole("link", { name: "Resumen", exact: true }).click();
  await page.getByLabel("Desde").fill("2026-08-01");
  await page.getByLabel("Hasta").fill("2026-08-31");
  await page.getByRole("button", { name: "Actualizar" }).click();
  const economic = page
    .getByRole("heading", { name: "Actividad del periodo" })
    .locator("..");
  const cash = page
    .getByRole("heading", { name: "Dinero disponible" })
    .locator("..");
  const worth = page.getByRole("heading", { name: "Patrimonio" }).locator("..");
  await expect(economic).toContainText(/Ingresos\s*250,00 €/);
  await expect(economic).toContainText(/Gastos\s*50,00 €/);
  await expect(economic).toContainText(/Resultado\s*200,00 €/);
  await expect(cash).toContainText(/Cobros\s*250,00 €/);
  await expect(cash).toContainText(/Pagos\s*50,00 €/);
  await expect(worth).toContainText(/Activos\s*1\.200,00 €/);

  await page.getByRole("link", { name: "Organizar" }).click();
  const expenseCategory = page
    .getByRole("listitem")
    .filter({ hasText: "Comida E2E" });
  page.once("dialog", (dialog) => dialog.accept("Comida hogar E2E"));
  await expenseCategory.getByRole("button", { name: "Renombrar" }).click();
  const renamedCategory = page
    .getByRole("listitem")
    .filter({ hasText: "Comida hogar E2E" });
  await expect(renamedCategory).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await renamedCategory.getByRole("button", { name: "Archivar" }).click();
  await expect(renamedCategory).toHaveCount(0);
  await page.getByRole("button", { name: "Archivadas" }).click();
  await expect(
    page.getByRole("listitem").filter({ hasText: "Comida hogar E2E" }),
  ).toBeVisible();

  await page.getByRole("link", { name: "Movimientos" }).click();
  await expect(
    page.getByRole("listitem").filter({ hasText: "Gasto E2E" }),
  ).toContainText("Comida hogar E2E (archivada)");
  await page.getByLabel("Añadir gasto").check();
  await expect(
    page.getByLabel("Categoría").getByRole("option", {
      name: "Comida hogar E2E",
    }),
  ).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(
    /\b(debe|haber|asiento)\b/i,
  );
});
