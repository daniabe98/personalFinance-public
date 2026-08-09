import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

import "../../test/setup";
import { ReportsSummary, type ReportsApi } from "./summary";

function reportsApi(): ReportsApi {
  return {
    economic: vi.fn().mockResolvedValue({
      ok: true,
      data: {
        start_date: "2026-06-01",
        end_date: "2026-06-30",
        income_cents: 250_050,
        expense_cents: -100_025,
        result_cents: 150_025,
        currency: "EUR",
        contributions: [
          {
            transaction_id: "income-june",
            amount_cents: 250_050,
            economic_date: "2026-06-03",
            cash_date: "2026-06-04",
            account_id: "bank",
            category_id: "salary",
            currency: "EUR",
          },
          {
            transaction_id: "reversal-july",
            amount_cents: -10_000,
            economic_date: "2026-07-01",
            cash_date: "2026-07-01",
            account_id: "bank",
            category_id: "salary",
            currency: "EUR",
          },
        ],
      },
    }),
    cash: vi.fn().mockResolvedValue({
      ok: true,
      data: {
        start_date: "2026-06-01",
        end_date: "2026-06-30",
        receipts_cents: 0,
        payments_cents: -100_025,
        net_cash_flow_cents: -100_025,
        currency: "EUR",
        contributions: [],
      },
    }),
    netWorth: vi.fn().mockResolvedValue({
      ok: true,
      data: {
        as_of: "2026-06-30",
        assets_cents: 900_719_925_474_099,
        liabilities_cents: -50_000,
        net_worth_cents: 900_719_925_424_099,
        currency: "EUR",
        contributions: [],
      },
    }),
  };
}

describe("ReportsSummary", () => {
  it("presents exact server totals and drill-down rows without charts", async () => {
    const user = userEvent.setup();
    const api = reportsApi();
    const { container } = render(
      <ReportsSummary
        api={api}
        initialInterval={{
          startDate: "2026-06-01",
          endDate: "2026-06-30",
        }}
      />,
    );

    expect(await screen.findByText("2.500,50 €")).toBeVisible();
    expect(screen.getAllByText("-1.000,25 €").length).toBeGreaterThan(0);
    expect(screen.getByText("1.500,25 €")).toBeVisible();
    expect(screen.getByText("0,00 €")).toBeVisible();
    expect(screen.getByText("-100,00 €")).toBeVisible();
    expect(screen.getByText("9.007.199.254.740,99 €")).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Ver movimiento income-june/ }),
    ).toHaveAttribute("href", "/movimientos?transaccion=income-june");
    expect(screen.getByText("2026-07-01")).toBeVisible();
    expect(container.querySelector("canvas, svg, img")).toBeNull();
    expect(container.textContent).not.toMatch(/\b(debe|haber|asiento)\b/i);
    expect((await axe.run(container)).violations).toEqual([]);

    await user.clear(screen.getByLabelText("Desde"));
    await user.type(screen.getByLabelText("Desde"), "2026-05-01");
    await user.click(screen.getByRole("button", { name: "Actualizar" }));
    expect(api.economic).toHaveBeenLastCalledWith("2026-05-01", "2026-06-30");
  });

  it("announces empty and error states without hiding report headings", async () => {
    const emptyApi = reportsApi();
    emptyApi.economic = vi.fn().mockResolvedValue({
      ok: true,
      data: {
        start_date: "2026-06-01",
        end_date: "2026-06-30",
        income_cents: 0,
        expense_cents: 0,
        result_cents: 0,
        contributions: [],
        currency: "EUR",
      },
    });
    render(
      <ReportsSummary
        api={emptyApi}
        initialInterval={{
          startDate: "2026-06-01",
          endDate: "2026-06-30",
        }}
      />,
    );
    expect(await screen.findByText("Sin actividad económica")).toBeVisible();
    expect(
      screen.getByRole("heading", { name: "Actividad del periodo" }),
    ).toBeVisible();
  });

  it("rejects unusable server responses instead of rounding money", async () => {
    const failedApi: ReportsApi = {
      ...reportsApi(),
      economic: vi.fn().mockResolvedValue({
        ok: false,
        message: "El servidor devolvió importes no válidos.",
      }),
    };
    render(
      <ReportsSummary
        api={failedApi}
        initialInterval={{
          startDate: "2026-06-01",
          endDate: "2026-06-30",
        }}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudieron cargar los informes",
    );
  });
});
