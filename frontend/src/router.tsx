import type { ComponentType } from "react";
import {
  createBrowserRouter,
  createMemoryRouter,
  Navigate,
  type RouterProviderProps,
} from "react-router-dom";

import type { AuthApi } from "./features/auth/api";
import { SessionProvider } from "./features/auth/session-provider";
import { CatalogPage } from "./features/catalog/page";
import { TransactionsPage } from "./features/transactions/page";
import { AppShell } from "./layout/app-shell";

export interface ControlRoutePages {
  readonly summary: ComponentType;
  readonly reconciliation: ComponentType;
  readonly settings: ComponentType;
}

export interface CreateAppRouterOptions {
  readonly authApi: AuthApi;
  readonly controlPages: ControlRoutePages;
  readonly initialEntries?: readonly string[];
}

export function createAppRouter(
  options: CreateAppRouterOptions,
): RouterProviderProps["router"] {
  const Summary = options.controlPages.summary;
  const Reconciliation = options.controlPages.reconciliation;
  const Settings = options.controlPages.settings;
  const routes = [
    {
      path: "/",
      element: (
        <SessionProvider api={options.authApi}>
          <AppShell />
        </SessionProvider>
      ),
      children: [
        { index: true, element: <Navigate replace to="/resumen" /> },
        { path: "resumen", element: <Summary /> },
        { path: "movimientos", element: <TransactionsPage /> },
        { path: "conciliar", element: <Reconciliation /> },
        { path: "organizar", element: <CatalogPage /> },
        { path: "ajustes", element: <Settings /> },
      ],
    },
  ];
  return options.initialEntries === undefined
    ? createBrowserRouter(routes)
    : createMemoryRouter(routes, {
        initialEntries: [...options.initialEntries],
      });
}
