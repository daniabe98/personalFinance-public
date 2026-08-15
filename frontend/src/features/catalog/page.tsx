import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { AccountResponse, CategoryResponse } from "../../api/schema";
import { createApiClient } from "../../api/client";
import { useCsrfToken } from "../auth/session-provider";
import { EmptyState, ErrorMessage, LoadingState } from "../../ui/feedback";
import { formatEurCents } from "../../lib/money";
import { createCatalogApi, type CatalogApi } from "./api";
import { AccountForm, CategoryForm } from "./forms";

type CatalogTab = "accounts" | "categories";

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
  const [activeTab, setActiveTab] = useState<CatalogTab>("accounts");
  const accountsTabRef = useRef<HTMLButtonElement>(null);
  const categoriesTabRef = useRef<HTMLButtonElement>(null);
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
  function activateTabFromKeyboard(
    event: React.KeyboardEvent<HTMLButtonElement>,
  ): void {
    let nextTab: CatalogTab;
    switch (event.key) {
      case "ArrowRight":
        nextTab = activeTab === "accounts" ? "categories" : "accounts";
        break;
      case "ArrowLeft":
        nextTab = activeTab === "accounts" ? "categories" : "accounts";
        break;
      case "Home":
        nextTab = "accounts";
        break;
      case "End":
        nextTab = "categories";
        break;
      default:
        return;
    }
    event.preventDefault();
    setActiveTab(nextTab);
    const nextTabRef =
      nextTab === "accounts" ? accountsTabRef : categoriesTabRef;
    nextTabRef.current?.focus();
  }
  if (state === "loading")
    return <LoadingState label="Cargando organización…" />;
  if (state === "error")
    return <ErrorMessage>No se pudo cargar la organización.</ErrorMessage>;
  return (
    <section aria-labelledby="catalog-title">
      <p className="eyebrow">Orden cotidiano</p>
      <h1 id="catalog-title">Organizar</h1>
      <div
        aria-label="Organizar catálogos"
        className="catalog-tabs"
        role="tablist"
      >
        <button
          aria-controls="accounts-panel"
          aria-selected={activeTab === "accounts"}
          className="catalog-tab"
          id="accounts-tab"
          onClick={() => setActiveTab("accounts")}
          onKeyDown={activateTabFromKeyboard}
          ref={accountsTabRef}
          role="tab"
          tabIndex={activeTab === "accounts" ? 0 : -1}
          type="button"
        >
          Cuentas
        </button>
        <button
          aria-controls="categories-panel"
          aria-selected={activeTab === "categories"}
          className="catalog-tab"
          id="categories-tab"
          onClick={() => setActiveTab("categories")}
          onKeyDown={activateTabFromKeyboard}
          ref={categoriesTabRef}
          role="tab"
          tabIndex={activeTab === "categories" ? 0 : -1}
          type="button"
        >
          Categorías
        </button>
      </div>
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
      <div
        aria-labelledby="accounts-tab"
        className="catalog-panel"
        hidden={activeTab !== "accounts"}
        id="accounts-panel"
        role="tabpanel"
      >
        <AccountForm api={api} onCreated={() => void load()} />
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
      </div>
      <div
        aria-labelledby="categories-tab"
        className="catalog-panel"
        hidden={activeTab !== "categories"}
        id="categories-panel"
        role="tabpanel"
      >
        <CategoryForm api={api} onCreated={() => void load()} />
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
