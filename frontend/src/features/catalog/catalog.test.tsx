import { render, screen } from "@testing-library/react";
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

describe("account and category organization", () => {
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
    render(
      <SessionProvider api={auth}>
        <CatalogPage api={api} />
      </SessionProvider>,
    );
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
