import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import "./test/setup";
import { App } from "./app";
import type { AuthApi } from "./features/auth/api";
import { createAppRouter } from "./router";

const authenticatedApi = (): AuthApi => ({
  session: vi.fn().mockResolvedValue({
    ok: true,
    principal: { user_id: "u", space_id: "s", username: "owner" },
    csrfToken: "csrf",
  }),
  login: vi.fn(),
  logout: vi.fn().mockResolvedValue({ ok: true }),
});

describe("protected application shell", () => {
  it("composes the application with its accessible default control pages", async () => {
    window.history.replaceState(null, "", "/resumen");
    render(<App authApi={authenticatedApi()} />);

    expect(
      await screen.findByRole("heading", { name: "Resumen" }),
    ).toBeVisible();
    expect(
      screen.getByText("Tu situación doméstica, reunida en un solo lugar."),
    ).toBeVisible();
  });

  it("creates the same-origin browser auth boundary when none is injected", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/resumen");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const path = String(input);
        if (path.includes("/auth/session")) {
          return Response.json({
            user_id: "u",
            space_id: "s",
            username: "owner",
            csrf_token: "refreshed",
          });
        }
        if (path.includes("/accounts")) {
          return Response.json([
            {
              id: "account",
              name: "Cuenta",
              is_reconcilable: true,
              is_archived: false,
            },
          ]);
        }
        if (path.includes("/reports/economic")) {
          return Response.json({
            income_cents: 0,
            expense_cents: 0,
            result_cents: 0,
            contributions: [],
          });
        }
        if (path.includes("/reports/cash-flow")) {
          return Response.json({
            receipts_cents: 0,
            payments_cents: 0,
            net_cash_flow_cents: 0,
          });
        }
        return Response.json({
          assets_cents: 0,
          liabilities_cents: 0,
          net_worth_cents: 0,
        });
      });

    render(<App />);

    expect(
      await screen.findByRole("heading", { name: "Resumen" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/session",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
    await user.click(screen.getByRole("link", { name: "Conciliar" }));
    expect(
      await screen.findByRole("heading", { name: "Conciliar" }),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/accounts?include_archived=false",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
    await user.click(screen.getByRole("link", { name: "Resumen" }));
    await user.click(screen.getByRole("button", { name: "Actualizar" }));
    expect(await screen.findByText("Sin actividad económica")).toBeVisible();
    vi.restoreAllMocks();
  });

  it("exposes five labelled destinations and injectable control pages", async () => {
    const user = userEvent.setup();
    const router = createAppRouter({
      authApi: authenticatedApi(),
      initialEntries: ["/resumen?intervalo=mes"],
      controlPages: {
        summary: () => <h1>Resumen doméstico</h1>,
        reconciliation: () => <h1>Comprobar movimientos</h1>,
        settings: () => <h1>Ajustes privados</h1>,
      },
    });
    const { container } = render(<RouterProvider router={router} />);

    expect(await screen.findByText("Resumen doméstico")).toBeVisible();
    const navigation = screen.getByRole("navigation", {
      name: "Navegación principal",
    });
    expect(navigation).toHaveTextContent("Resumen");
    expect(navigation).toHaveTextContent("Movimientos");
    expect(navigation).toHaveTextContent("Conciliar");
    expect(navigation).toHaveTextContent("Organizar");
    expect(navigation).toHaveTextContent("Ajustes");
    expect(screen.getByRole("link", { name: /Resumen/ })).toHaveAttribute(
      "aria-current",
      "page",
    );

    await user.click(screen.getByRole("link", { name: /Conciliar/ }));
    expect(await screen.findByText("Comprobar movimientos")).toBeVisible();
    expect((await axe.run(container)).violations).toEqual([]);
  });

  it("does not render the protected shell for an anonymous session", async () => {
    const router = createAppRouter({
      authApi: {
        ...authenticatedApi(),
        session: vi
          .fn()
          .mockResolvedValue({ ok: false, reason: "unauthorized" }),
      },
      initialEntries: ["/movimientos?estado=borrador"],
      controlPages: {
        summary: () => <h1>Resumen</h1>,
        reconciliation: () => <h1>Conciliar</h1>,
        settings: () => <h1>Ajustes</h1>,
      },
    });
    render(<RouterProvider router={router} />);

    expect(
      await screen.findByRole("heading", { name: "Acceder" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("navigation", { name: "Navegación principal" }),
    ).not.toBeInTheDocument();
  });
});
