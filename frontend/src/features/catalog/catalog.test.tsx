import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../test/setup";
import type { ApiClient, ApiRequestOptions, ApiResult } from "../../api/client";
import { SessionProvider } from "../auth/session-provider";
import type { AuthApi } from "../auth/api";
import { createCatalogApi, type CatalogApi } from "./api";
import { CatalogPage } from "./page";

const auth: AuthApi = {
  session: vi.fn().mockResolvedValue({
    ok: true,
    principal: { user_id: "u", space_id: "s", username: "owner" },
  }),
  login: vi.fn(),
  logout: vi.fn(),
};
const ok = <T,>(data: T) =>
  Promise.resolve({ ok: true as const, data, status: 200 });

function createCatalogStub(): CatalogApi {
  return {
    listAccounts: vi.fn(() =>
      ok([
        {
          id: "account-active",
          name: "Casa",
          kind: "ASSET" as const,
          is_archived: false,
          is_reconcilable: true,
          balance_cents: 0,
          currency: "EUR" as const,
        },
        {
          id: "account-archived",
          name: "Cuenta anterior",
          kind: "ASSET" as const,
          is_archived: true,
          is_reconcilable: false,
          balance_cents: 0,
          currency: "EUR" as const,
        },
      ]),
    ),
    listCategories: vi.fn(() =>
      ok([
        {
          id: "category-active",
          name: "Compras",
          kind: "EXPENSE" as const,
          is_archived: false,
        },
        {
          id: "category-archived",
          name: "Suscripciones anteriores",
          kind: "EXPENSE" as const,
          is_archived: true,
        },
      ]),
    ),
    createAccount: vi.fn(),
    createCategory: vi.fn(),
    renameAccount: vi.fn(),
    renameCategory: vi.fn(),
    setAccountArchived: vi.fn((id, isArchived) =>
      ok({
        id,
        name: "Cuenta anterior",
        kind: "ASSET" as const,
        is_archived: isArchived,
        is_reconcilable: false,
        balance_cents: 0,
        currency: "EUR" as const,
      }),
    ),
    setCategoryArchived: vi.fn((id, isArchived) =>
      ok({
        id,
        name: "Suscripciones anteriores",
        kind: "EXPENSE" as const,
        is_archived: isArchived,
      }),
    ),
  };
}

function renderCatalog(api: CatalogApi): void {
  render(
    <SessionProvider api={auth}>
      <CatalogPage api={api} />
    </SessionProvider>,
  );
}

describe("account and category organization", () => {
  it("associates one active panel with accessible account and category tabs", async () => {
    const api = createCatalogStub();
    renderCatalog(api);

    const tablist = await screen.findByRole("tablist", {
      name: "Organizar catálogos",
    });
    const accountsTab = screen.getByRole("tab", { name: "Cuentas" });
    const categoriesTab = screen.getByRole("tab", { name: "Categorías" });
    const accountsPanel = document.getElementById("accounts-panel");
    const categoriesPanel = document.getElementById("categories-panel");

    expect(tablist).toContainElement(accountsTab);
    expect(accountsTab).toHaveAttribute("id", "accounts-tab");
    expect(accountsTab).toHaveAttribute("aria-controls", "accounts-panel");
    expect(accountsTab).toHaveAttribute("aria-selected", "true");
    expect(accountsTab).toHaveAttribute("tabindex", "0");
    expect(categoriesTab).toHaveAttribute("id", "categories-tab");
    expect(categoriesTab).toHaveAttribute("aria-controls", "categories-panel");
    expect(categoriesTab).toHaveAttribute("aria-selected", "false");
    expect(categoriesTab).toHaveAttribute("tabindex", "-1");
    expect(accountsPanel).toHaveAttribute("role", "tabpanel");
    expect(accountsPanel).toHaveAttribute("aria-labelledby", "accounts-tab");
    expect(accountsPanel).not.toHaveAttribute("hidden");
    expect(categoriesPanel).toHaveAttribute("role", "tabpanel");
    expect(categoriesPanel).toHaveAttribute(
      "aria-labelledby",
      "categories-tab",
    );
    expect(categoriesPanel).toHaveAttribute("hidden");
  });

  it("moves and activates tab focus with Arrow, Home and End keys", async () => {
    const user = userEvent.setup();
    renderCatalog(createCatalogStub());
    const accountsTab = await screen.findByRole("tab", { name: "Cuentas" });
    const categoriesTab = screen.getByRole("tab", { name: "Categorías" });

    accountsTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(categoriesTab).toHaveFocus();
    expect(categoriesTab).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowLeft}");
    expect(accountsTab).toHaveFocus();
    expect(accountsTab).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{End}");
    expect(categoriesTab).toHaveFocus();
    expect(categoriesTab).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{Home}");
    expect(accountsTab).toHaveFocus();
    expect(accountsTab).toHaveAttribute("aria-selected", "true");
  });

  it("keeps valid form state mounted while changing tabs", async () => {
    const user = userEvent.setup();
    renderCatalog(createCatalogStub());
    await screen.findByRole("tab", { name: "Cuentas" });
    const accountName = screen.getByLabelText("Nombre", {
      selector: "#account-name",
    });
    await user.type(accountName, "Ahorro familiar");

    await user.click(screen.getByRole("tab", { name: "Categorías" }));
    const categoryName = screen.getByLabelText("Nombre", {
      selector: "#category-name",
    });
    await user.type(categoryName, "Casa y hogar");

    await user.click(screen.getByRole("tab", { name: "Cuentas" }));
    expect(accountName).toHaveValue("Ahorro familiar");
    await user.click(screen.getByRole("tab", { name: "Categorías" }));
    expect(categoryName).toHaveValue("Casa y hogar");
  });

  it("shares the active or archived filter and preserves catalog actions", async () => {
    const user = userEvent.setup();
    const api = createCatalogStub();
    renderCatalog(api);
    await screen.findByRole("tab", { name: "Cuentas" });

    await user.click(screen.getByRole("button", { name: "Archivadas" }));
    expect(screen.getByText("Cuenta anterior")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Reactivar" }));
    await waitFor(() =>
      expect(api.setAccountArchived).toHaveBeenCalledWith(
        "account-archived",
        false,
      ),
    );

    await user.click(screen.getByRole("tab", { name: "Categorías" }));
    expect(screen.getByText("Suscripciones anteriores")).toBeVisible();
    expect(screen.queryByText("Compras")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reactivar" }));
    await waitFor(() =>
      expect(api.setCategoryArchived).toHaveBeenCalledWith(
        "category-archived",
        false,
      ),
    );

    await user.click(screen.getByRole("button", { name: "Activas" }));
    expect(screen.getByText("Compras")).toBeVisible();
    expect(
      screen.queryByText("Suscripciones anteriores"),
    ).not.toBeInTheDocument();
  });

  it("maps every catalog operation to the closed generated boundary", async () => {
    const calls: string[] = [];
    const client: ApiClient = {
      async request<T>(
        path: `/api/v1/${string}`,
        options?: ApiRequestOptions<T>,
      ): Promise<ApiResult<T>> {
        calls.push(`${options?.method ?? "GET"} ${path}`);
        const value: unknown = path.startsWith("/api/v1/accounts")
          ? path.includes("?")
            ? []
            : {
                id: "a",
                name: "Casa",
                kind: "ASSET",
                is_archived: false,
                is_reconcilable: true,
                balance_cents: 0,
                currency: "EUR",
              }
          : path.includes("?")
            ? []
            : {
                id: "c",
                name: "Hogar",
                kind: "EXPENSE",
                is_archived: false,
              };
        // The fake exercises the adapter's route and validator wiring.
        expect(options?.validate?.(value)).toBe(true);
        return { ok: true, data: value as T, status: 200 };
      },
    };
    const api = createCatalogApi(client);

    await api.listAccounts(true);
    await api.listCategories(false);
    await api.createAccount({
      name: "Casa",
      kind: "ASSET",
      is_reconcilable: true,
    });
    await api.createCategory({ name: "Hogar", kind: "EXPENSE" });
    await api.renameAccount("a/1", "Casa nueva");
    await api.renameCategory("c/1", "Hogar nuevo");
    await api.setAccountArchived("a/1", true);
    await api.setAccountArchived("a/1", false);
    await api.setCategoryArchived("c/1", true);
    await api.setCategoryArchived("c/1", false);

    expect(calls).toEqual([
      "GET /api/v1/accounts?include_archived=true",
      "GET /api/v1/categories?include_archived=false",
      "POST /api/v1/accounts",
      "POST /api/v1/categories",
      "PATCH /api/v1/accounts/a%2F1",
      "PATCH /api/v1/categories/c%2F1",
      "POST /api/v1/accounts/a%2F1/archive",
      "POST /api/v1/accounts/a%2F1/unarchive",
      "POST /api/v1/categories/c%2F1/archive",
      "POST /api/v1/categories/c%2F1/unarchive",
    ]);
  });

  it("creates everyday account shapes and never offers deletion", async () => {
    const user = userEvent.setup();
    const api: CatalogApi = {
      listAccounts: vi.fn(() => ok([])),
      listCategories: vi.fn(() => ok([])),
      createAccount: vi.fn((input) =>
        ok({
          id: "a",
          ...input,
          is_archived: false,
          balance_cents: 0,
          currency: "EUR" as const,
        }),
      ),
      createCategory: vi.fn((input) =>
        ok({ id: "c", ...input, is_archived: false }),
      ),
      renameAccount: vi.fn(),
      renameCategory: vi.fn(),
      setAccountArchived: vi.fn(),
      setCategoryArchived: vi.fn(),
    };
    renderCatalog(api);
    await screen.findByRole("heading", { name: "Organizar" });
    await user.type(
      screen.getByLabelText("Nombre", { selector: "#account-name" }),
      "Casa",
    );
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(api.createAccount).toHaveBeenCalledWith({
      name: "Casa",
      kind: "ASSET",
      is_reconcilable: true,
    });
    expect(
      screen.queryByRole("button", { name: /eliminar/i }),
    ).not.toBeInTheDocument();
  });
});
