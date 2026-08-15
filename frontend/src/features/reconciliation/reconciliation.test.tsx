import { fireEvent, render, screen } from "@testing-library/react";
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

function deferred<T>(): {
  readonly promise: Promise<T>;
  readonly resolve: (value: T) => void;
} {
  let resolvePromise: ((value: T) => void) | undefined;
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });
  return {
    promise,
    resolve(value) {
      if (resolvePromise === undefined) {
        throw new Error("Deferred promise is not initialized.");
      }
      resolvePromise(value);
    },
  };
}

describe("ReconciliationPage", () => {
  it("guides selection using only the canonical server difference", async () => {
    const user = userEvent.setup();
    const api = reconciliationApi();
    const { container } = render(<ReconciliationPage api={api} />);

    expect(screen.getByRole("heading", { name: "Revisión" })).toBeVisible();
    expect(screen.getByText("Fecha pendiente")).toBeVisible();
    expect(screen.getByText("Saldo real pendiente")).toBeVisible();

    await screen.findByRole("option", { name: "Cuenta corriente" });
    await user.selectOptions(
      screen.getByLabelText("Cuenta"),
      "account-current",
    );
    await user.type(screen.getByLabelText("Fecha de corte"), "2026-06-30");
    await user.type(screen.getByLabelText("Saldo real"), "1500,00");

    expect(await screen.findByText("Base inicial")).toBeVisible();
    expect(screen.getByText("Saldo al empezar")).toBeVisible();
    expect(screen.getByText("Nómina")).toBeVisible();
    expect(screen.getByText("Cuenta lista")).toBeVisible();
    expect(screen.getByText("Fecha lista")).toBeVisible();
    expect(screen.getByText("Saldo real listo")).toBeVisible();
    expect(api.preview).not.toHaveBeenCalled();
    expect(
      screen.queryByRole("button", { name: "Completar conciliación" }),
    ).not.toBeInTheDocument();

    const income = screen.getByRole("checkbox", { name: /Nómina/ });
    income.focus();
    await user.keyboard(" ");

    expect(await screen.findByText("Cuadrado")).toBeVisible();
    expect(screen.getAllByText("1.500,00 €")).toHaveLength(2);
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
    expect(await screen.findByText("Sin movimientos pendientes")).toBeVisible();

    const failedApi: ReconciliationApi = {
      ...reconciliationApi(),
      candidates: vi.fn().mockResolvedValue({
        ok: false,
        message: "No se pudieron cargar los movimientos.",
      }),
    };
    rerender(<ReconciliationPage api={failedApi} />);
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
    expect(screen.getByText("Cuenta pendiente")).toBeVisible();
    expect(api.candidates).not.toHaveBeenCalled();
    expect(api.preview).not.toHaveBeenCalled();
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

  it("does not request a preview until valid fields include a selected entry", async () => {
    const user = userEvent.setup();
    const api = reconciliationApi();
    render(<ReconciliationPage api={api} />);

    await screen.findByRole("option", { name: "Cuenta corriente" });
    expect(api.preview).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Fecha de corte"), "2026-06-30");
    expect(api.preview).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText("Saldo real"), "importe incorrecto");
    expect(api.preview).not.toHaveBeenCalled();
    expect(screen.getByText("Saldo real pendiente")).toBeVisible();

    await user.clear(screen.getByLabelText("Saldo real"));
    fireEvent.change(screen.getByLabelText("Saldo real"), {
      target: { value: "1500,00" },
    });

    expect(api.preview).not.toHaveBeenCalled();
    expect(screen.getByText("Cuenta lista")).toBeVisible();
    expect(screen.getByText("Fecha lista")).toBeVisible();
    expect(screen.getByText("Saldo real listo")).toBeVisible();

    await user.click(
      await screen.findByRole("checkbox", { name: /Saldo al empezar/ }),
    );
    expect(api.preview).toHaveBeenCalledWith(
      expect.objectContaining({
        account_id: "account-current",
        cutoff_date: "2026-06-30",
        actual_balance_cents: 150_000,
        selected_entry_ids: ["entry-opening"],
      }),
    );
    expect(await screen.findByText("Con diferencia")).toBeVisible();
  });

  it("keeps only the latest preview response and latest error", async () => {
    const user = userEvent.setup();
    const first = deferred<Awaited<ReturnType<ReconciliationApi["preview"]>>>();
    const second =
      deferred<Awaited<ReturnType<ReconciliationApi["preview"]>>>();
    const api: ReconciliationApi = {
      ...reconciliationApi(),
      preview: vi
        .fn()
        .mockImplementationOnce(() => first.promise)
        .mockImplementationOnce(() => second.promise),
    };
    render(<ReconciliationPage api={api} />);

    await screen.findByRole("option", { name: "Cuenta corriente" });
    await user.type(screen.getByLabelText("Fecha de corte"), "2026-06-30");
    fireEvent.change(screen.getByLabelText("Saldo real"), {
      target: { value: "1500,00" },
    });
    expect(api.preview).not.toHaveBeenCalled();
    const income = await screen.findByRole("checkbox", { name: /Nómina/ });
    await user.click(income);
    expect(await screen.findByText("Calculando…")).toBeVisible();
    const opening = screen.getByRole("checkbox", { name: /Saldo al empezar/ });
    await user.click(opening);
    expect(api.preview).toHaveBeenCalledTimes(2);

    second.resolve({
      ok: true,
      data: preview(["entry-income", "entry-opening"]),
    });
    expect(await screen.findByText("Cuadrado")).toBeVisible();
    first.resolve({ ok: false, message: "Error antiguo" });

    expect(await screen.findByText("Cuadrado")).toBeVisible();
    expect(screen.queryByText("Error antiguo")).not.toBeInTheDocument();
  });

  it("renders the exact fallback for a nullable legacy description", async () => {
    const user = userEvent.setup();
    const api: ReconciliationApi = {
      ...reconciliationApi(),
      candidates: vi.fn().mockResolvedValue({
        ok: true,
        data: [{ ...candidates[0], description: null }],
      }),
    };
    render(<ReconciliationPage api={api} />);

    await screen.findByRole("option", { name: "Cuenta corriente" });
    await user.type(screen.getByLabelText("Fecha de corte"), "2026-06-30");

    expect(await screen.findByText("Sin descripción")).toBeVisible();
  });

  it("binds completion to the current preview and prevents duplicate submits", async () => {
    const user = userEvent.setup();
    const pendingPreview =
      deferred<Awaited<ReturnType<ReconciliationApi["preview"]>>>();
    const latestPreview =
      deferred<Awaited<ReturnType<ReconciliationApi["preview"]>>>();
    const pendingCompletion =
      deferred<Awaited<ReturnType<ReconciliationApi["complete"]>>>();
    const api: ReconciliationApi = {
      ...reconciliationApi(),
      preview: vi
        .fn()
        .mockResolvedValueOnce({ ok: true, data: preview(["entry-income"]) })
        .mockImplementationOnce(() => pendingPreview.promise)
        .mockImplementationOnce(() => latestPreview.promise),
      complete: vi.fn(() => pendingCompletion.promise),
    };
    render(<ReconciliationPage api={api} />);

    await screen.findByRole("option", { name: "Cuenta corriente" });
    await user.type(screen.getByLabelText("Fecha de corte"), "2026-06-30");
    fireEvent.change(screen.getByLabelText("Saldo real"), {
      target: { value: "1500,00" },
    });
    await user.click(await screen.findByRole("checkbox", { name: /Nómina/ }));

    const complete = await screen.findByRole("button", {
      name: "Completar conciliación",
    });
    expect(complete).toBeEnabled();

    await user.click(
      screen.getByRole("checkbox", { name: /Saldo al empezar/ }),
    );
    expect(complete).toBeDisabled();
    pendingPreview.resolve({
      ok: true,
      data: preview(["entry-income", "entry-opening"]),
    });
    expect(await screen.findByText("Cuadrado")).toBeVisible();
    expect(complete).toBeEnabled();

    fireEvent.click(complete);
    fireEvent.click(complete);
    expect(api.complete).toHaveBeenCalledTimes(1);
    expect(complete).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Saldo real"), {
      target: { value: "1600,00" },
    });
    pendingCompletion.resolve({
      ok: true,
      data: preview(["entry-income", "entry-opening"]),
    });

    expect(
      await screen.findByRole("button", { name: "Completar conciliación" }),
    ).toBeDisabled();
    expect(
      screen.queryByText("Conciliación completada"),
    ).not.toBeInTheDocument();
  });
});
