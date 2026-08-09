import { useMemo, useRef, useState } from "react";

import type {
  AccountResponse,
  CategoryResponse,
  TransactionKind,
  TransactionResponse,
} from "../../api/schema";
import { formatEurCents, parseEurCents } from "../../lib/money";
import { localCalendarDate } from "../../lib/local-date";
import { ErrorMessage } from "../../ui/feedback";
import type { MovementInput, TransactionsApi } from "./api";

type EntryKind = Exclude<TransactionKind, "REVERSAL">;
const actions: readonly { readonly kind: EntryKind; readonly label: string }[] =
  [
    { kind: "INCOME", label: "Añadir ingreso" },
    { kind: "EXPENSE", label: "Añadir gasto" },
    { kind: "TRANSFER", label: "Mover dinero" },
    { kind: "OPENING", label: "Indicar saldo inicial" },
  ];

export function TransactionForm({
  accounts,
  api,
  categories,
  draft = null,
  onCancelEdit,
  onSaved,
}: {
  readonly accounts: readonly AccountResponse[];
  readonly api: TransactionsApi;
  readonly categories: readonly CategoryResponse[];
  readonly draft?: TransactionResponse | null;
  readonly onCancelEdit?: () => void;
  readonly onSaved: () => void;
}): React.JSX.Element {
  const today = localCalendarDate();
  const draftKind: EntryKind =
    draft?.kind !== undefined && draft.kind !== "REVERSAL"
      ? draft.kind
      : "INCOME";
  const [kind, setKind] = useState<EntryKind>(draftKind);
  const [amount, setAmount] = useState(
    draft?.amount_cents === null || draft === null
      ? ""
      : formatEurCents(draft.amount_cents).replace(" €", ""),
  );
  const [economicDate, setEconomicDate] = useState(
    draft?.economic_date ?? today,
  );
  const [cashDate, setCashDate] = useState(
    draft?.cash_date ?? draft?.economic_date ?? today,
  );
  const [accountId, setAccountId] = useState(draft?.account_id ?? "");
  const [destinationId, setDestinationId] = useState(
    draft?.destination_account_id ?? "",
  );
  const [categoryId, setCategoryId] = useState(draft?.category_id ?? "");
  const [description, setDescription] = useState(draft?.description ?? "");
  const [summary, setSummary] = useState<MovementInput | null>(null);
  const [error, setError] = useState<string | null>(null);
  const retry = useRef<{
    readonly signature: string;
    readonly key: string;
  } | null>(null);
  const eligibleAccounts = useMemo(
    () => accounts.filter((item) => !item.is_archived),
    [accounts],
  );
  const eligibleCategories = useMemo(
    () => categories.filter((item) => !item.is_archived && item.kind === kind),
    [categories, kind],
  );

  function prepare(): void {
    const parsedAmount = parseEurCents(amount);
    if (
      !parsedAmount.ok ||
      parsedAmount.value <= 0 ||
      accountId === "" ||
      economicDate === ""
    ) {
      setError("Completa una cantidad positiva, una cuenta y la fecha.");
      return;
    }
    if ((kind === "INCOME" || kind === "EXPENSE") && categoryId === "") {
      setError("Elige una categoría.");
      return;
    }
    if (
      kind === "TRANSFER" &&
      (destinationId === "" || destinationId === accountId)
    ) {
      setError("Elige una cuenta de destino distinta.");
      return;
    }
    setSummary({
      kind,
      amount_cents: parsedAmount.value,
      economic_date: economicDate,
      description: description.trim() || null,
      account_id: accountId,
      ...(kind === "TRANSFER" ? { destination_account_id: destinationId } : {}),
      ...(kind === "INCOME" || kind === "EXPENSE"
        ? { category_id: categoryId }
        : {}),
      ...(kind !== "OPENING" ? { cash_date: cashDate || economicDate } : {}),
    });
    setError(null);
  }
  async function save(mode: "draft" | "post"): Promise<void> {
    if (summary === null) return;
    if (mode === "draft") {
      const result =
        draft === null
          ? await api.createDraft(summary)
          : await api.updateDraft(draft.id, summary);
      if (!result.ok) return setError("No se pudo guardar el borrador.");
      setSummary(null);
      onSaved();
      return;
    }
    const signature = JSON.stringify(summary);
    if (retry.current?.signature !== signature)
      retry.current = { signature, key: crypto.randomUUID() };
    const result =
      draft === null
        ? await api.post(summary, retry.current.key)
        : await api.postDraft(
            draft.id,
            summary.cash_date ?? null,
            retry.current.key,
          );
    if (!result.ok)
      return setError(
        result.error.kind === "conflict"
          ? "La operación ya existe o cambió. Revisa los datos."
          : "No se guardó ningún movimiento. Inténtalo de nuevo.",
      );
    retry.current = null;
    setSummary(null);
    setAmount("");
    onSaved();
  }
  if (summary !== null)
    return (
      <section
        className="surface-solid movement-summary"
        aria-labelledby="summary-title"
      >
        <h2 id="summary-title">Revisa antes de guardar</h2>
        <p>
          <strong>
            {actions.find((action) => action.kind === summary.kind)?.label}
          </strong>
        </p>
        <p className="money">{formatEurCents(summary.amount_cents)}</p>
        <p>Fecha del movimiento: {summary.economic_date}</p>
        {summary.cash_date ? (
          <p>Fecha en la cuenta: {summary.cash_date}</p>
        ) : null}
        {error ? <ErrorMessage>{error}</ErrorMessage> : null}
        <div className="actions">
          <button type="button" onClick={() => void save("post")}>
            Contabilizar
          </button>
          <button
            className="secondary"
            type="button"
            onClick={() => void save("draft")}
          >
            Guardar borrador
          </button>
          <button
            className="secondary"
            type="button"
            onClick={() => setSummary(null)}
          >
            Volver a editar
          </button>
        </div>
      </section>
    );
  return (
    <form
      className="surface-solid movement-form"
      onSubmit={(event) => {
        event.preventDefault();
        prepare();
      }}
    >
      <fieldset>
        <legend>¿Qué quieres hacer?</legend>
        <div className="choice-grid">
          {actions.map((action) => (
            <label key={action.kind}>
              <input
                checked={kind === action.kind}
                name="movement-kind"
                type="radio"
                value={action.kind}
                onChange={() => {
                  setKind(action.kind);
                  setCategoryId("");
                }}
              />
              {action.label}
            </label>
          ))}
        </div>
      </fieldset>
      {draft === null ? null : <p>Editando el borrador seleccionado.</p>}
      {error ? <ErrorMessage>{error}</ErrorMessage> : null}
      <div className="form-grid">
        <div className="field">
          <label htmlFor="amount">Cantidad en euros</label>
          <input
            id="amount"
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="account">
            {kind === "TRANSFER" ? "Cuenta de origen" : "Cuenta"}
          </label>
          <select
            id="account"
            value={accountId}
            onChange={(event) => setAccountId(event.target.value)}
          >
            <option value="">Elige una</option>
            {eligibleAccounts.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        {kind === "TRANSFER" ? (
          <div className="field">
            <label htmlFor="destination">Cuenta de destino</label>
            <select
              id="destination"
              value={destinationId}
              onChange={(event) => setDestinationId(event.target.value)}
            >
              <option value="">Elige una</option>
              {eligibleAccounts.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        {kind === "INCOME" || kind === "EXPENSE" ? (
          <div className="field">
            <label htmlFor="category">Categoría</label>
            <select
              id="category"
              value={categoryId}
              onChange={(event) => setCategoryId(event.target.value)}
            >
              <option value="">Elige una</option>
              {eligibleCategories.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        <div className="field">
          <label htmlFor="economic-date">Fecha del movimiento</label>
          <input
            id="economic-date"
            type="date"
            value={economicDate}
            onChange={(event) => {
              setEconomicDate(event.target.value);
              setCashDate(event.target.value);
            }}
          />
        </div>
        {kind !== "OPENING" ? (
          <div className="field">
            <label htmlFor="cash-date">Fecha en la cuenta</label>
            <input
              id="cash-date"
              type="date"
              value={cashDate}
              onChange={(event) => setCashDate(event.target.value)}
            />
          </div>
        ) : null}
        <div className="field">
          <label htmlFor="description">Descripción (opcional)</label>
          <input
            id="description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>
      </div>
      <div className="actions">
        <button type="submit">Revisar movimiento</button>
        {draft !== null && onCancelEdit !== undefined ? (
          <button className="secondary" type="button" onClick={onCancelEdit}>
            Cancelar edición
          </button>
        ) : null}
      </div>
    </form>
  );
}
