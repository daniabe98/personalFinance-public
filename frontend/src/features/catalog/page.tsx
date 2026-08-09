import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AccountResponse, CategoryResponse } from "../../api/schema";
import { createApiClient } from "../../api/client";
import { useCsrfToken } from "../auth/session-provider";
import { EmptyState, ErrorMessage, LoadingState } from "../../ui/feedback";
import { formatEurCents } from "../../lib/money";
import { createCatalogApi, type CatalogApi } from "./api";
import { AccountForm, CategoryForm } from "./forms";

function ItemActions({
  archived,
  name,
  onArchive,
  onRename,
}: {
  readonly archived: boolean;
  readonly name: string;
  readonly onArchive: () => Promise<void>;
  readonly onRename: (name: string) => Promise<void>;
}): React.JSX.Element {
  const trigger = useRef<HTMLButtonElement>(null);
  return (
    <div className="actions">
      <button
        className="secondary"
        type="button"
        onClick={() => {
          const next = window.prompt("Nuevo nombre", name);
          if (next?.trim()) void onRename(next.trim());
        }}
      >
        Renombrar
      </button>
      <button
        className={archived ? "secondary" : "danger"}
        ref={trigger}
        type="button"
        onClick={() => {
          if (!archived && !window.confirm(`¿Archivar ${name}?`)) return;
          void onArchive().finally(() => trigger.current?.focus());
        }}
      >
        {archived ? "Reactivar" : "Archivar"}
      </button>
    </div>
  );
}

export function CatalogPage({
  api: suppliedApi,
}: {
  readonly api?: CatalogApi;
}): React.JSX.Element {
  const csrf = useCsrfToken();
  const api = useMemo(
    () =>
      suppliedApi ??
      createCatalogApi(createApiClient({ getCsrfToken: () => csrf })),
    [csrf, suppliedApi],
  );
  const [showArchived, setShowArchived] = useState(false);
  const [accounts, setAccounts] = useState<readonly AccountResponse[]>([]);
  const [categories, setCategories] = useState<readonly CategoryResponse[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const load = useCallback(async () => {
    setState("loading");
    const [accountResult, categoryResult] = await Promise.all([
      api.listAccounts(true),
      api.listCategories(true),
    ]);
    if (!accountResult.ok || !categoryResult.ok) return setState("error");
    setAccounts(accountResult.data);
    setCategories(categoryResult.data);
    setState("ready");
  }, [api]);
  useEffect(() => void load(), [load]);
  const visibleAccounts = accounts.filter(
    (item) => item.is_archived === showArchived,
  );
  const visibleCategories = categories.filter(
    (item) => item.is_archived === showArchived,
  );
  if (state === "loading")
    return <LoadingState label="Cargando organización…" />;
  if (state === "error")
    return <ErrorMessage>No se pudo cargar la organización.</ErrorMessage>;
  return (
    <section aria-labelledby="catalog-title">
      <p className="eyebrow">Orden cotidiano</p>
      <h1 id="catalog-title">Organizar</h1>
      <fieldset className="segmented">
        <legend className="sr-only">Estado de elementos</legend>
        <button
          className={!showArchived ? "" : "secondary"}
          onClick={() => setShowArchived(false)}
          type="button"
        >
          Activas
        </button>
        <button
          className={showArchived ? "" : "secondary"}
          onClick={() => setShowArchived(true)}
          type="button"
        >
          Archivadas
        </button>
      </fieldset>
      {!showArchived ? (
        <div className="form-grid">
          <AccountForm api={api} onCreated={() => void load()} />
          <CategoryForm api={api} onCreated={() => void load()} />
        </div>
      ) : null}
      <div className="catalog-grid">
        <section
          className="surface-solid catalog-list"
          aria-labelledby="accounts-title"
        >
          <h2 id="accounts-title">Cuentas</h2>
          {visibleAccounts.length === 0 ? (
            <EmptyState title="Sin cuentas">
              No hay cuentas en esta vista.
            </EmptyState>
          ) : (
            <ul className="item-list">
              {visibleAccounts.map((item) => (
                <li key={item.id}>
                  <strong>{item.name}</strong>
                  <span>
                    {item.kind === "ASSET" ? "Dinero y bienes" : "Deudas"} ·{" "}
                    <span className="money">
                      {formatEurCents(item.balance_cents)}
                    </span>
                  </span>
                  <span>
                    {item.is_reconcilable
                      ? "Se comprueba con extractos"
                      : "Sin comprobación por extracto"}
                  </span>
                  <ItemActions
                    archived={item.is_archived}
                    name={item.name}
                    onArchive={async () => {
                      await api.setAccountArchived(item.id, !item.is_archived);
                      await load();
                    }}
                    onRename={async (name) => {
                      await api.renameAccount(item.id, name);
                      await load();
                    }}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
        <section
          className="surface-solid catalog-list"
          aria-labelledby="categories-title"
        >
          <h2 id="categories-title">Categorías</h2>
          {visibleCategories.length === 0 ? (
            <EmptyState title="Sin categorías">
              No hay categorías en esta vista.
            </EmptyState>
          ) : (
            <ul className="item-list">
              {visibleCategories.map((item) => (
                <li key={item.id}>
                  <strong>{item.name}</strong>
                  <span>{item.kind === "INCOME" ? "Ingresos" : "Gastos"}</span>
                  <ItemActions
                    archived={item.is_archived}
                    name={item.name}
                    onArchive={async () => {
                      await api.setCategoryArchived(item.id, !item.is_archived);
                      await load();
                    }}
                    onRename={async (name) => {
                      await api.renameCategory(item.id, name);
                      await load();
                    }}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </section>
  );
}
