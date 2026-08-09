import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

import "../../test/setup";
import { ReconciliationPage, type ReconciliationApi } from "./page";

const candidates = [
  {
    entry_id: "entry-opening",
    transaction_id: "transaction-opening",
    eligibility_date: "2026-06-01",
    effect_cents: 100_000,
    currency: "EUR" as const,
    description: "Saldo al empezar",
    kind: "OPENING" as const,
    status: "POSTED" as const,
  },
  {
    entry_id: "entry-income",
    transaction_id: "transaction-income",
    eligibility_date: "2026-06-17",
    effect_cents: 50_000,
    currency: "EUR" as const,
    description: "Nómina",
    kind: "INCOME" as const,
    status: "POSTED" as const,
  },
] as const;

function preview(selectedEntryIds: readonly string[]) {
  const isBalanced = selectedEntryIds.includes("entry-income");
  return {
    reconciliation_id: "preview",
    status: "PREVIEW",
    account_id: "account-current",
    cutoff_date: "2026-06-30",
    actual_balance_cents: 150_000,
    prior_completed_cents: 100_000,
    selected_effect_cents: isBalanced ? 50_000 : 0,
    checked_balance_cents: isBalanced ? 150_000 : 100_000,
    difference_cents: isBalanced ? 0 : 50_000,
    selected_entry_ids: selectedEntryIds,
    currency: "EUR" as const,
  };
}

function reconciliationApi(): ReconciliationApi {
  return {
    accounts: vi.fn().mockResolvedValue({
      ok: true,
      data: [
        {
          id: "account-current",
          name: "Cuenta corriente",
          is_reconcilable: true,
          is_archived: false,
        },
      ],
    }),
    candidates: vi.fn().mockResolvedValue({ ok: true, data: candidates }),
    preview: vi.fn().mockImplementation(async (request) => ({
      ok: true,
      data: preview(request.selected_entry_ids),
    })),
    complete: vi.fn().mockImplementation(async (request) => ({
      ok: true,
      data: { ...preview(request.selected_entry_ids), status: "COMPLETED" },
    })),
  };
}

describe("ReconciliationPage", () => {
  it("guides selection using only the canonical server difference", async () => {
    const user = userEvent.setup();
    const api = reconciliationApi();
    const { container } = render(<ReconciliationPage api={api} />);

    await screen.findByRole("option", { name: "Cuenta corriente" });
    await user.selectOptions(
      screen.getByLabelText("Cuenta"),
      "account-current",
    );
    await user.type(screen.getByLabelText("Fecha de corte"), "2026-06-30");
    await user.type(screen.getByLabelText("Saldo real"), "1500,00");
    await user.click(
      screen.getByRole("button", { name: "Revisar movimientos" }),
    );

    expect(await screen.findByText("Base inicial")).toBeVisible();
    expect(screen.getByText("Saldo al empezar")).toBeVisible();
    expect(screen.getByText("Nómina")).toBeVisible();
    expect(screen.getByText("Diferencia")).toBeVisible();
    expect(screen.getAllByText("500,00 €").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: "Completar conciliación" }),
    ).toBeDisabled();

    const income = screen.getByRole("checkbox", { name: /Nómina/ });
    income.focus();
    await user.keyboard(" ");

    expect(await screen.findByText("La diferencia es cero.")).toBeVisible();
    expect(screen.getByText("1.500,00 €")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Completar conciliación" }),
    ).toBeEnabled();
    expect(api.preview).toHaveBeenLastCalledWith(
      expect.objectContaining({
        actual_balance_cents: 150_000,
        selected_entry_ids: ["entry-income"],
      }),
    );

    await user.click(
      screen.getByRole("button", { name: "Completar conciliación" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Conciliación completada",
    );
    expect(api.complete).toHaveBeenCalledTimes(1);
    expect((await axe.run(container)).violations).toEqual([]);
    expect(container.textContent).not.toMatch(/\b(debe|haber|asiento)\b/i);
  });

  it("announces empty and failed candidate queries", async () => {
    const user = userEvent.setup();
    const emptyApi: ReconciliationApi = {
      ...reconciliationApi(),
      candidates: vi.fn().mockResolvedValue({ ok: true, data: [] }),
    };
    const { rerender } = render(<ReconciliationPage api={emptyApi} />);

    await screen.findByRole("option", { name: "Cuenta corriente" });
    await user.selectOptions(
      screen.getByLabelText("Cuenta"),
      "account-current",
    );
    await user.type(screen.getByLabelText("Fecha de corte"), "2026-06-30");
    await user.type(screen.getByLabelText("Saldo real"), "0");
    await user.click(
      screen.getByRole("button", { name: "Revisar movimientos" }),
    );
    expect(await screen.findByText("Sin movimientos pendientes")).toBeVisible();

    const failedApi: ReconciliationApi = {
      ...reconciliationApi(),
      candidates: vi.fn().mockResolvedValue({
        ok: false,
        message: "No se pudieron cargar los movimientos.",
      }),
    };
    rerender(<ReconciliationPage api={failedApi} />);
    await user.click(
      screen.getByRole("button", { name: "Revisar movimientos" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudieron cargar los movimientos",
    );
  });

  it("explains when no conciliable account is available", async () => {
    const user = userEvent.setup();
    const api: ReconciliationApi = {
      ...reconciliationApi(),
      accounts: vi.fn().mockResolvedValue({ ok: true, data: [] }),
    };
    render(<ReconciliationPage api={api} />);

    await screen.findByRole("option", { name: "Sin cuentas conciliables" });
    await user.type(screen.getByLabelText("Fecha de corte"), "2026-06-30");
    await user.type(screen.getByLabelText("Saldo real"), "0");
    await user.click(
      screen.getByRole("button", { name: "Revisar movimientos" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Crea una cuenta conciliable",
    );
    expect(api.candidates).not.toHaveBeenCalled();
  });

  it("announces an account catalog failure", async () => {
    const api: ReconciliationApi = {
      ...reconciliationApi(),
      accounts: vi.fn().mockResolvedValue({
        ok: false,
        message: "No se pudieron cargar las cuentas.",
      }),
    };
    render(<ReconciliationPage api={api} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudieron cargar las cuentas",
    );
  });
});
