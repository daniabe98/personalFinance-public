import { useState } from "react";

import type { AccountKind, CategoryKind } from "../../api/schema";
import { ErrorMessage } from "../../ui/feedback";
import type { CatalogApi } from "./api";

export function AccountForm({
  api,
  onCreated,
}: {
  readonly api: CatalogApi;
  readonly onCreated: () => void;
}): React.JSX.Element {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<AccountKind>("ASSET");
  const [reconcilable, setReconcilable] = useState(true);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (name.trim() === "") return setError("Escribe un nombre.");
    const result = await api.createAccount({
      name: name.trim(),
      kind,
      is_reconcilable: reconcilable,
    });
    if (!result.ok) return setError("No se pudo crear la cuenta.");
    setName("");
    setError(null);
    onCreated();
  }
  return (
    <form
      className="surface-solid compact-form"
      onSubmit={(event) => void submit(event)}
    >
      <h3>Nueva cuenta</h3>
      {error === null ? null : <ErrorMessage>{error}</ErrorMessage>}
      <div className="field">
        <label htmlFor="account-name">Nombre</label>
        <input
          id="account-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="account-kind">Tipo</label>
        <select
          id="account-kind"
          value={kind}
          onChange={(event) => setKind(event.target.value as AccountKind)}
        >
          <option value="ASSET">Dinero y bienes</option>
          <option value="LIABILITY">Deudas</option>
        </select>
      </div>
      <label className="check-field">
        <input
          checked={reconcilable}
          onChange={(event) => setReconcilable(event.target.checked)}
          type="checkbox"
        />
        Se puede comprobar con extractos
      </label>
      <button type="submit">Crear cuenta</button>
    </form>
  );
}

export function CategoryForm({
  api,
  onCreated,
}: {
  readonly api: CatalogApi;
  readonly onCreated: () => void;
}): React.JSX.Element {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<CategoryKind>("EXPENSE");
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (name.trim() === "") return setError("Escribe un nombre.");
    const result = await api.createCategory({ name: name.trim(), kind });
    if (!result.ok) return setError("No se pudo crear la categoría.");
    setName("");
    setError(null);
    onCreated();
  }
  return (
    <form
      className="surface-solid compact-form"
      onSubmit={(event) => void submit(event)}
    >
      <h3>Nueva categoría</h3>
      {error === null ? null : <ErrorMessage>{error}</ErrorMessage>}
      <div className="field">
        <label htmlFor="category-name">Nombre</label>
        <input
          id="category-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="category-kind">Uso</label>
        <select
          id="category-kind"
          value={kind}
          onChange={(event) => setKind(event.target.value as CategoryKind)}
        >
          <option value="EXPENSE">Gastos</option>
          <option value="INCOME">Ingresos</option>
        </select>
      </div>
      <button type="submit">Crear categoría</button>
    </form>
  );
}
