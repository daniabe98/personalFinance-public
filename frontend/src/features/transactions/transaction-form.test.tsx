import axe from "axe-core";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import "../../test/setup";
import type { ApiClient, ApiRequestOptions, ApiResult } from "../../api/client";
import type { TransactionResponse } from "../../api/schema";
import type { AuthApi } from "../auth/api";
import { SessionProvider } from "../auth/session-provider";
import type { CatalogApi } from "../catalog/api";
import { createTransactionsApi, type TransactionsApi } from "./api";
import { TransactionForm } from "./form";
import { TransactionHistory } from "./history";
import { TransactionsPage } from "./page";
import { ReversalDialog } from "./reversal-dialog";

const ok = <T,>(data: T) =>
  Promise.resolve({ ok: true as const, data, status: 200 });
const transaction = (
  values: Partial<TransactionResponse> = {},
): TransactionResponse => ({
  id: "tx-1",
  kind: "INCOME",
  status: "DRAFT",
  status_label: "Borrador",
  economic_date: "2026-07-23",
  cash_date: "2026-07-23",
  description: "Nómina",
  amount_cents: 1234,
  account_id: "a",
  category_id: "c",
  destination_account_id: null,
  original_transaction_id: null,
  reversal_transaction_id: null,
  corrected_original_transaction_id: null,
  replacement_transaction_id: null,
  ...values,
});
const auth: AuthApi = {
  session: vi.fn(() =>
    Promise.resolve({
      ok: true as const,
      principal: { user_id: "u", space_id: "s", username: "owner" },
      csrfToken: "csrf",
    }),
  ),
  login: vi.fn(),
  logout: vi.fn(),
};

describe("closed movement entry", () => {
  it("progressively prepares exact cents and posts with an idempotency key", async () => {
    const user = userEvent.setup();
    const api: TransactionsApi = {
      list: vi.fn(),
      createDraft: vi.fn(),
      updateDraft: vi.fn(),
      discardDraft: vi.fn(),
      postDraft: vi.fn(),
      reverse: vi.fn(),
      post: vi.fn(() =>
        ok({
          transaction_id: "t",
          status: "POSTED",
          replayed: false,
          replacement_transaction_id: null,
        }),
      ),
    };
    render(
      <TransactionForm
        api={api}
        accounts={[
          {
            id: "a",
            name: "Banco",
            kind: "ASSET",
            is_archived: false,
            is_reconcilable: true,
            balance_cents: 0,
            currency: "EUR",
          },
        ]}
        categories={[
          { id: "c", name: "Nómina", kind: "INCOME", is_archived: false },
        ]}
        onSaved={() => undefined}
      />,
    );
    expect(screen.getByText("Añadir ingreso")).toBeVisible();
    expect(screen.getByText("Añadir gasto")).toBeVisible();
    expect(screen.getByText("Mover dinero")).toBeVisible();
    expect(screen.getByText("Indicar saldo inicial")).toBeVisible();
    await user.type(screen.getByLabelText("Cantidad en euros"), "12,34");
    await user.selectOptions(screen.getByLabelText("Cuenta"), "a");
    await user.selectOptions(screen.getByLabelText("Categoría"), "c");
    await user.type(screen.getByLabelText("Descripción"), "Nómina mensual");
    await user.click(
      screen.getByRole("button", { name: "Revisar movimiento" }),
    );
    expect(screen.getByText("12,34 €")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Contabilizar" }));
    expect(api.post).toHaveBeenCalledWith(
      expect.objectContaining({
        amount_cents: 1234,
        description: "Nómina mensual",
        kind: "INCOME",
      }),
      expect.any(String),
    );
    expect(
      screen.queryByText(/\b(debe|haber|asiento)\b/i),
    ).not.toBeInTheDocument();
  });

  it("requires a trimmed description of 1–500 characters before review", async () => {
    const user = userEvent.setup();
    const api: TransactionsApi = {
      list: vi.fn(),
      createDraft: vi.fn(() => ok(transaction())),
      updateDraft: vi.fn(),
      discardDraft: vi.fn(),
      postDraft: vi.fn(),
      reverse: vi.fn(),
      post: vi.fn(),
    };
    render(
      <TransactionForm
        api={api}
        accounts={[
          {
            id: "a",
            name: "Banco",
            kind: "ASSET",
            is_archived: false,
            is_reconcilable: true,
            balance_cents: 0,
            currency: "EUR",
          },
        ]}
        categories={[
          { id: "c", name: "Nómina", kind: "INCOME", is_archived: false },
        ]}
        onSaved={() => undefined}
      />,
    );

    const description = screen.getByLabelText("Descripción");
    expect(description).toBeRequired();
    expect(description).toHaveAttribute("maxlength", "500");
    expect(description).toHaveAccessibleDescription("1–500 caracteres.");
    await user.type(screen.getByLabelText("Cantidad en euros"), "12,34");
    await user.selectOptions(screen.getByLabelText("Cuenta"), "a");
    await user.selectOptions(screen.getByLabelText("Categoría"), "c");

    await user.type(description, "   ");
    await user.click(
      screen.getByRole("button", { name: "Revisar movimiento" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Escribe una descripción de entre 1 y 500 caracteres.",
    );
    expect(
      screen.queryByRole("heading", { name: "Revisa antes de guardar" }),
    ).not.toBeInTheDocument();

    fireEvent.change(description, { target: { value: "x".repeat(501) } });
    const form = description.closest("form");
    expect(form).not.toBeNull();
    if (form === null) throw new Error("Transaction form is missing");
    fireEvent.submit(form);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Escribe una descripción de entre 1 y 500 caracteres.",
    );

    fireEvent.change(description, {
      target: { value: "  Nómina mensual  " },
    });
    await user.click(
      screen.getByRole("button", { name: "Revisar movimiento" }),
    );
    expect(screen.getByText("Nómina mensual")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
    expect(api.createDraft).toHaveBeenCalledWith(
      expect.objectContaining({ description: "Nómina mensual" }),
    );
  });

  it("requires a legacy draft description and persists it before posting", async () => {
    const user = userEvent.setup();
    const legacyDraft = transaction({ description: null });
    const updatedDraft = transaction({ description: "Nómina recuperada" });
    const api: TransactionsApi = {
      list: vi.fn(),
      createDraft: vi.fn(),
      updateDraft: vi.fn(() => ok(updatedDraft)),
      discardDraft: vi.fn(),
      postDraft: vi.fn(() =>
        ok({
          transaction_id: legacyDraft.id,
          status: "POSTED",
          replayed: false,
          replacement_transaction_id: null,
        }),
      ),
      reverse: vi.fn(),
      post: vi.fn(),
    };
    render(
      <TransactionForm
        accounts={[
          {
            id: "a",
            name: "Banco",
            kind: "ASSET",
            is_archived: false,
            is_reconcilable: true,
            balance_cents: 0,
            currency: "EUR",
          },
        ]}
        api={api}
        categories={[
          { id: "c", name: "Nómina", kind: "INCOME", is_archived: false },
        ]}
        draft={legacyDraft}
        onSaved={() => undefined}
      />,
    );

    expect(screen.getByLabelText("Descripción")).toHaveValue("");
    await user.type(screen.getByLabelText("Descripción"), "Nómina recuperada");
    await user.click(
      screen.getByRole("button", { name: "Revisar movimiento" }),
    );
    await user.click(screen.getByRole("button", { name: "Contabilizar" }));

    expect(api.updateDraft).toHaveBeenCalledWith(
      legacyDraft.id,
      expect.objectContaining({ description: "Nómina recuperada" }),
    );
    expect(api.postDraft).toHaveBeenCalledWith(
      legacyDraft.id,
      legacyDraft.cash_date,
      expect.any(String),
    );
    expect(vi.mocked(api.updateDraft).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(api.postDraft).mock.invocationCallOrder[0] ?? 0,
    );
  });

  it("preloads and updates a draft before posting that same draft", async () => {
    const user = userEvent.setup();
    const draft = transaction();
    const api: TransactionsApi = {
      list: vi.fn(),
      createDraft: vi.fn(),
      updateDraft: vi.fn(() => ok(draft)),
      discardDraft: vi.fn(),
      postDraft: vi.fn(() =>
        ok({
          transaction_id: draft.id,
          status: "POSTED",
          replayed: false,
          replacement_transaction_id: null,
        }),
      ),
      reverse: vi.fn(),
      post: vi.fn(),
    };
    const { rerender } = render(
      <TransactionForm
        accounts={[
          {
            id: "a",
            name: "Banco",
            kind: "ASSET",
            is_archived: false,
            is_reconcilable: true,
            balance_cents: 0,
            currency: "EUR",
          },
        ]}
        api={api}
        categories={[
          { id: "c", name: "Nómina", kind: "INCOME", is_archived: false },
        ]}
        draft={draft}
        onCancelEdit={() => undefined}
        onSaved={() => undefined}
      />,
    );
    expect(screen.getByDisplayValue("12,34")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Revisar movimiento" }),
    );
    await user.click(screen.getByRole("button", { name: "Guardar borrador" }));
    expect(api.updateDraft).toHaveBeenCalledWith(
      "tx-1",
      expect.objectContaining({ amount_cents: 1234 }),
    );
    rerender(
      <TransactionForm
        accounts={[
          {
            id: "a",
            name: "Banco",
            kind: "ASSET",
            is_archived: false,
            is_reconcilable: true,
            balance_cents: 0,
            currency: "EUR",
          },
        ]}
        api={api}
        categories={[
          { id: "c", name: "Nómina", kind: "INCOME", is_archived: false },
        ]}
        draft={draft}
        onSaved={() => undefined}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Revisar movimiento" }),
    );
    await user.click(screen.getByRole("button", { name: "Contabilizar" }));
    expect(api.postDraft).toHaveBeenCalledWith(
      "tx-1",
      "2026-07-23",
      expect.any(String),
    );
  });

  it("shows immutable history actions and confirms a compensating movement", async () => {
    const user = userEvent.setup();
    const api: TransactionsApi = {
      list: vi.fn(),
      createDraft: vi.fn(),
      updateDraft: vi.fn(),
      discardDraft: vi.fn(() => ok(null)),
      postDraft: vi.fn(),
      post: vi.fn(),
      reverse: vi.fn(() =>
        ok({
          transaction_id: "rev",
          status: "POSTED",
          replayed: false,
          replacement_transaction_id: null,
        }),
      ),
    };
    const edit = vi.fn();
    const reverse = vi.fn();
    render(
      <>
        <TransactionHistory
          api={api}
          items={[
            transaction(),
            transaction({
              id: "posted",
              status: "POSTED",
              original_transaction_id: "old",
              reversal_transaction_id: "rev",
            }),
            transaction({ id: "void", status: "VOIDED" }),
          ]}
          onChange={() => undefined}
          onEdit={edit}
          onReverse={reverse}
        />
        <ReversalDialog
          api={api}
          onClose={() => undefined}
          onComplete={() => undefined}
          transactionId="posted"
        />
      </>,
    );
    expect(screen.getAllByText("12,34 €")).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "Editar borrador" }));
    await user.click(
      screen.getByRole("button", {
        name: "Anular con un movimiento compensatorio",
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Confirmar compensación" }),
    );
    expect(edit).toHaveBeenCalled();
    expect(reverse).toHaveBeenCalled();
    expect(api.reverse).toHaveBeenCalledWith(
      "posted",
      {
        economic_date: expect.any(String),
        cash_date: expect.any(String),
      },
      expect.any(String),
    );
    expect(
      screen.getByText(/La descripción se generará.*movimiento original/i),
    ).toBeVisible();
    expect(
      screen.queryByRole("textbox", { name: /descripción/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps every state and relationship explicit, navigable and non-destructive", async () => {
    const api: TransactionsApi = {
      list: vi.fn(),
      createDraft: vi.fn(),
      updateDraft: vi.fn(),
      discardDraft: vi.fn(),
      postDraft: vi.fn(),
      post: vi.fn(),
      reverse: vi.fn(),
    };
    const { container } = render(
      <TransactionHistory
        accounts={[
          {
            id: "a",
            name: "Cuenta antigua",
            kind: "ASSET",
            is_archived: true,
            is_reconcilable: true,
            balance_cents: 0,
            currency: "EUR",
          },
        ]}
        api={api}
        categories={[
          {
            id: "c",
            name: "Categoría antigua",
            kind: "INCOME",
            is_archived: true,
          },
        ]}
        items={[
          transaction({ id: "draft" }),
          transaction({
            id: "posted",
            status: "POSTED",
            replacement_transaction_id: "replacement",
          }),
          transaction({
            id: "checked",
            status: "RECONCILED",
            reversal_transaction_id: "reversal",
          }),
          transaction({
            id: "reversal",
            kind: "REVERSAL",
            status: "POSTED",
            original_transaction_id: "checked",
          }),
          transaction({
            id: "replacement",
            corrected_original_transaction_id: "posted",
          }),
          transaction({ id: "voided", status: "VOIDED" }),
        ]}
        onChange={() => undefined}
        onEdit={() => undefined}
        onReverse={() => undefined}
      />,
    );

    for (const label of [
      "Estado: Borrador",
      "Estado: Contabilizado",
      "Estado: Comprobado",
      "Estado: Anulado",
    ]) {
      expect(screen.getAllByLabelText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText("Cuenta antigua (archivada)")).toHaveLength(6);
    expect(screen.getAllByText("Categoría antigua (archivada)")).toHaveLength(
      6,
    );
    expect(screen.getByRole("link", { name: "replacement" })).toHaveAttribute(
      "href",
      "#movement-replacement",
    );
    expect(screen.getByRole("link", { name: "checked" })).toHaveAttribute(
      "href",
      "#movement-checked",
    );
    expect(container.querySelector("#movement-replacement")).not.toBeNull();
    expect(
      screen.getAllByRole("button", { name: /Editar borrador/ }),
    ).toHaveLength(2);
    expect(
      screen.queryByRole("button", { name: /borrar|eliminar/i }),
    ).not.toBeInTheDocument();
    expect((await axe.run(container)).violations).toEqual([]);
  });

  it("maps every closed transaction endpoint through the API adapter", async () => {
    const calls: string[] = [];
    const client: ApiClient = {
      async request<T>(
        path: `/api/v1/${string}`,
        options?: ApiRequestOptions<T>,
      ): Promise<ApiResult<T>> {
        calls.push(`${options?.method ?? "GET"} ${path}`);
        const data: unknown =
          path.includes("/drafts") &&
          !path.endsWith("/post") &&
          options?.method !== "DELETE"
            ? transaction()
            : path.includes("?limit")
              ? [transaction()]
              : path.endsWith("/reverse") ||
                  path.endsWith("/post") ||
                  path.match(/\/(opening|income|expense|transfer)$/)
                ? {
                    transaction_id: "tx",
                    status: "POSTED",
                    replayed: false,
                    replacement_transaction_id: null,
                  }
                : null;
        // This typed fake deliberately supplies the response selected above.
        return { ok: true, data: data as T, status: 200 };
      },
    };
    const api = createTransactionsApi(client);
    const input = {
      kind: "INCOME" as const,
      economic_date: "2026-07-23",
      description: "Nómina",
      amount_cents: 100,
      account_id: "a",
      category_id: "c",
      cash_date: "2026-07-23",
    };
    await api.list();
    await api.createDraft(input);
    await api.updateDraft("tx", input);
    await api.discardDraft("tx");
    await api.postDraft("tx", null, "key");
    await api.post(input, "key");
    await api.post(
      { ...input, kind: "TRANSFER", destination_account_id: "b" },
      "key",
    );
    await api.reverse(
      "tx",
      { economic_date: "2026-07-23", cash_date: null },
      "key",
    );
    expect(calls).toHaveLength(8);
  });

  it("loads the complete movements page from injected APIs", async () => {
    const api: TransactionsApi = {
      list: vi.fn(() => ok([transaction({ status: "POSTED" })])),
      createDraft: vi.fn(),
      updateDraft: vi.fn(),
      discardDraft: vi.fn(),
      postDraft: vi.fn(),
      post: vi.fn(),
      reverse: vi.fn(),
    };
    const catalogApi: CatalogApi = {
      listAccounts: vi.fn(() =>
        ok([
          {
            id: "a",
            name: "Banco",
            kind: "ASSET" as const,
            is_archived: false,
            is_reconcilable: true,
            balance_cents: 0,
            currency: "EUR" as const,
          },
        ]),
      ),
      listCategories: vi.fn(() =>
        ok([
          {
            id: "c",
            name: "Nómina",
            kind: "INCOME" as const,
            is_archived: false,
          },
        ]),
      ),
      createAccount: vi.fn(),
      createCategory: vi.fn(),
      renameAccount: vi.fn(),
      renameCategory: vi.fn(),
      setAccountArchived: vi.fn(),
      setCategoryArchived: vi.fn(),
    };
    render(
      <SessionProvider api={auth}>
        <TransactionsPage api={api} catalogApi={catalogApi} />
      </SessionProvider>,
    );
    expect(
      await screen.findByRole("heading", { name: "Movimientos" }),
    ).toBeVisible();
    expect(screen.getAllByText("Nómina")).toHaveLength(3);
    expect(catalogApi.listAccounts).toHaveBeenCalledWith(true);
    expect(catalogApi.listCategories).toHaveBeenCalledWith(true);
  });
});
