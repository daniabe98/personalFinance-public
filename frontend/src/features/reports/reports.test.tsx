import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

import "../../test/setup";
import { EconomicReportView } from "./economic";
import { ReportsSummary, type ReportsApi } from "./summary";

function reportsApi(): ReportsApi {
  return {
    economic: vi.fn().mockResolvedValue({
      ok: true,
      data: {
        start_date: "2026-08-01",
        end_date: "2026-08-31",
        income_cents: 250_050,
        expense_cents: 100_025,
        result_cents: 150_025,
        currency: "EUR",
        contributions: [
          {
            transaction_id: "6fa940fb-2f6a-467a-8b7d-1f4d734fcf8a",
            amount_cents: 250_050,
            economic_date: "2026-08-10",
            cash_date: "2026-08-10",
            account_id: null,
            category_id: "salary",
            currency: "EUR",
          },
          {
            transaction_id: "a8fa92c8-2124-4071-ac01-b74e10447b78",
            amount_cents: 110_025,
            economic_date: "2026-08-12",
            cash_date: "2026-08-12",
            account_id: null,
            category_id: "housing",
            currency: "EUR",
          },
          {
            transaction_id: "336d8214-c004-4b95-b30a-1032d4811d0f",
            amount_cents: -10_000,
            economic_date: "2026-08-18",
            cash_date: "2026-08-18",
            account_id: null,
            category_id: "housing-reversal",
            currency: "EUR",
          },
        ],
      },
    }),
    cash: vi.fn().mockResolvedValue({
      ok: true,
      data: {
        start_date: "2026-08-01",
        end_date: "2026-08-31",
        receipts_cents: 0,
        payments_cents: 100_025,
        net_cash_flow_cents: -100_025,
        currency: "EUR",
        contributions: [
          {
            transaction_id: "a8fa92c8-2124-4071-ac01-b74e10447b78",
            amount_cents: 110_025,
            economic_date: "2026-08-12",
            cash_date: "2026-08-12",
            account_id: "bank",
            category_id: null,
            currency: "EUR",
          },
          {
            transaction_id: "336d8214-c004-4b95-b30a-1032d4811d0f",
            amount_cents: -10_000,
            economic_date: "2026-08-18",
            cash_date: "2026-08-18",
            account_id: "bank",
            category_id: null,
            currency: "EUR",
          },
        ],
      },
    }),
    netWorth: vi.fn().mockResolvedValue({
      ok: true,
      data: {
        as_of: "2026-08-31",
        assets_cents: 900_719_925_474_099,
        liabilities_cents: 50_000,
        net_worth_cents: 900_719_925_424_099,
        currency: "EUR",
        contributions: [
          {
            transaction_id: "asset-balance",
            amount_cents: 900_719_925_474_099,
            economic_date: "2026-08-01",
            cash_date: null,
            account_id: "bank",
            category_id: null,
            currency: "EUR",
          },
          {
            transaction_id: "liability-balance",
            amount_cents: 50_000,
            economic_date: "2026-08-01",
            cash_date: null,
            account_id: "mortgage",
            category_id: null,
            currency: "EUR",
          },
        ],
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
          startDate: "2026-08-01",
          endDate: "2026-08-31",
        }}
      />,
    );

    const heading = await screen.findByRole("heading", {
      name: "Actividad del periodo",
    });
    const economicSection = heading.closest("section");
    if (economicSection === null) {
      throw new Error(
        "El informe económico debe conservar su sección semántica",
      );
    }
    const economic = within(economicSection);

    expect(economic.getByText("2.500,50 €")).toBeVisible();
    expect(economic.getByText("1.000,25 €")).toBeVisible();
    expect(economic.getByText("1.500,25 €")).toBeVisible();
    expect(screen.getByText("0,00 €")).toBeVisible();
    expect(screen.getByText("9.007.199.254.740,99 €")).toBeVisible();

    const localizedDate = economic.getByText("10 ago 2026");
    expect(localizedDate.tagName).toBe("TIME");
    expect(localizedDate).toHaveAttribute("datetime", "2026-08-10");
    expect(economic.getAllByText("Movimiento")).toHaveLength(3);
    expect(economic.queryByText(/^Ingreso$/)).not.toBeInTheDocument();
    expect(economic.queryByText(/^Gasto$/)).not.toBeInTheDocument();
    expect(economic.getByText("+2.500,50 €")).toBeVisible();
    expect(economic.getByText("+1.100,25 €")).toBeVisible();
    expect(economic.getByText("−100,00 €")).toBeVisible();

    const firstDetail = economic.getByRole("link", {
      name: "Ver detalle de Movimiento, +2.500,50 €, 10 ago 2026, 1 de 3",
    });
    expect(firstDetail).toHaveTextContent(/^Ver detalle$/);
    expect(firstDetail).toHaveAttribute(
      "href",
      "/movimientos?transaccion=6fa940fb-2f6a-467a-8b7d-1f4d734fcf8a",
    );
    expect(
      economic.getByRole("link", {
        name: "Ver detalle de Movimiento, −100,00 €, 18 ago 2026, 3 de 3",
      }),
    ).toHaveTextContent(/^Ver detalle$/);
    expect(container.querySelector("canvas, svg, img")).toBeNull();
    expect(container.textContent).not.toMatch(/\b(debe|haber|asiento)\b/i);
    expect((await axe.run(container)).violations).toEqual([]);

    await user.clear(screen.getByLabelText("Desde"));
    await user.type(screen.getByLabelText("Desde"), "2026-07-01");
    await user.click(screen.getByRole("button", { name: "Actualizar" }));
    expect(api.economic).toHaveBeenLastCalledWith("2026-07-01", "2026-08-31");
  });

  it("presents zero contribution only as a defensive neutral state", () => {
    render(
      <EconomicReportView
        report={{
          income_cents: 0,
          expense_cents: 0,
          result_cents: 0,
          contributions: [
            {
              transaction_id: "defensive-zero",
              amount_cents: 0,
              economic_date: "2026-08-10",
            },
          ],
        }}
      />,
    );

    const contribution = within(screen.getByRole("listitem"));
    expect(contribution.getByText("Sin impacto")).toBeVisible();
    expect(contribution.getByText("0,00 €")).toBeVisible();
    const localizedDate = contribution.getByText("10 ago 2026");
    expect(localizedDate.tagName).toBe("TIME");
    expect(localizedDate).toHaveAttribute("datetime", "2026-08-10");
    const detail = contribution.getByRole("link", {
      name: "Ver detalle de Sin impacto, 0,00 €, 10 ago 2026, 1 de 1",
    });
    expect(detail).toHaveTextContent(/^Ver detalle$/);
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
