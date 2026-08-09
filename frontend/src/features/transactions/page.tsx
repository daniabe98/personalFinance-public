import { useCallback, useEffect, useMemo, useState } from "react";

import { createApiClient } from "../../api/client";
import type {
  AccountResponse,
  CategoryResponse,
  TransactionResponse,
} from "../../api/schema";
import { ErrorMessage, LoadingState } from "../../ui/feedback";
import { useCsrfToken } from "../auth/session-provider";
import { createCatalogApi, type CatalogApi } from "../catalog/api";
import { createTransactionsApi, type TransactionsApi } from "./api";
import { TransactionForm } from "./form";
import { TransactionHistory } from "./history";
import { ReversalDialog } from "./reversal-dialog";

export function TransactionsPage({
  api: suppliedApi,
  catalogApi: suppliedCatalogApi,
}: {
  readonly api?: TransactionsApi;
  readonly catalogApi?: CatalogApi;
}): React.JSX.Element {
  const csrf = useCsrfToken();
  const client = useMemo(
    () => createApiClient({ getCsrfToken: () => csrf }),
    [csrf],
  );
  const api = useMemo(
    () => suppliedApi ?? createTransactionsApi(client),
    [client, suppliedApi],
  );
  const catalogApi = useMemo(
    () => suppliedCatalogApi ?? createCatalogApi(client),
    [client, suppliedCatalogApi],
  );
  const [items, setItems] = useState<readonly TransactionResponse[]>([]);
  const [accounts, setAccounts] = useState<readonly AccountResponse[]>([]);
  const [categories, setCategories] = useState<readonly CategoryResponse[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [reversing, setReversing] = useState<TransactionResponse | null>(null);
  const [editing, setEditing] = useState<TransactionResponse | null>(null);
  const load = useCallback(async () => {
    const [transactions, accountResult, categoryResult] = await Promise.all([
      api.list(),
      catalogApi.listAccounts(true),
      catalogApi.listCategories(true),
    ]);
    if (!transactions.ok || !accountResult.ok || !categoryResult.ok)
      return setState("error");
    setItems(transactions.data);
    setAccounts(accountResult.data);
    setCategories(categoryResult.data);
    setState("ready");
  }, [api, catalogApi]);
  useEffect(() => void load(), [load]);
  if (state === "loading")
    return <LoadingState label="Cargando movimientos…" />;
  if (state === "error")
    return <ErrorMessage>No se pudieron cargar los movimientos.</ErrorMessage>;
  return (
    <section aria-labelledby="movements-title">
      <p className="eyebrow">Día a día</p>
      <h1 id="movements-title">Movimientos</h1>
      <TransactionForm
        accounts={accounts}
        api={api}
        categories={categories}
        draft={editing}
        key={editing?.id ?? "new"}
        onCancelEdit={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          void load();
        }}
      />
      <section aria-labelledby="history-title">
        <h2 id="history-title">Historial</h2>
        <TransactionHistory
          accounts={accounts}
          api={api}
          categories={categories}
          items={items}
          onChange={() => void load()}
          onEdit={setEditing}
          onReverse={setReversing}
        />
      </section>
      {reversing ? (
        <ReversalDialog
          api={api}
          transactionId={reversing.id}
          onClose={() => setReversing(null)}
          onComplete={() => {
            setReversing(null);
            void load();
          }}
        />
      ) : null}
    </section>
  );
}
