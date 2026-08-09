import { useEffect, useState } from "react";

import { parseEurCents } from "../../lib/money";
import {
  ReconciliationEntryList,
  type ReconciliationCandidate,
} from "./entry-list";
import { ReconciliationSummary, type ReconciliationPreview } from "./summary";

type Result<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly message: string };

interface ReconciliationRequest {
  readonly account_id: string;
  readonly cutoff_date: string;
  readonly actual_balance_cents: number;
  readonly selected_entry_ids: readonly string[];
}

export interface ReconciliationAccount {
  readonly id: string;
  readonly name: string;
  readonly is_reconcilable: boolean;
  readonly is_archived: boolean;
}

export interface ReconciliationApi {
  accounts(): Promise<Result<readonly ReconciliationAccount[]>>;
  candidates(
    accountId: string,
    cutoffDate: string,
  ): Promise<Result<readonly ReconciliationCandidate[]>>;
  preview(
    request: ReconciliationRequest,
  ): Promise<Result<ReconciliationPreview>>;
  complete(
    request: ReconciliationRequest,
  ): Promise<Result<ReconciliationPreview>>;
}

export function ReconciliationPage({
  api,
}: {
  readonly api: ReconciliationApi;
}): React.JSX.Element {
  const [account, setAccount] = useState("");
  const [accounts, setAccounts] = useState<readonly ReconciliationAccount[]>(
    [],
  );
  const [cutoff, setCutoff] = useState("");
  const [actual, setActual] = useState("");
  const [candidates, setCandidates] =
    useState<readonly ReconciliationCandidate[]>();
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [preview, setPreview] = useState<ReconciliationPreview>();
  const [error, setError] = useState("");
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    let active = true;
    void api.accounts().then((result) => {
      if (!active) return;
      if (result.ok) {
        const available = result.data.filter(
          (item) => item.is_reconcilable && !item.is_archived,
        );
        setAccounts(available);
        setAccount((current) => current || available[0]?.id || "");
      } else {
        setError(result.message);
      }
    });
    return () => {
      active = false;
    };
  }, [api]);

  function request(ids: ReadonlySet<string>): ReconciliationRequest | null {
    const parsed = parseEurCents(actual);
    if (!parsed.ok) {
      setError(parsed.message);
      return null;
    }
    return {
      account_id: account,
      cutoff_date: cutoff,
      actual_balance_cents: parsed.value,
      selected_entry_ids: [...ids],
    };
  }

  async function review(): Promise<void> {
    setError("");
    setCompleted(false);
    if (account === "") {
      setError("Crea una cuenta conciliable antes de revisar movimientos.");
      return;
    }
    const candidateResult = await api.candidates(account, cutoff);
    if (!candidateResult.ok) {
      setError(candidateResult.message);
      return;
    }
    setCandidates(candidateResult.data);
    const payload = request(new Set());
    if (payload === null) return;
    const result = await api.preview(payload);
    if (result.ok) setPreview(result.data);
    else setError(result.message);
  }

  async function select(entryId: string, checked: boolean): Promise<void> {
    const next = new Set(selected);
    if (checked) next.add(entryId);
    else next.delete(entryId);
    setSelected(next);
    const payload = request(next);
    if (payload === null) return;
    const result = await api.preview(payload);
    if (result.ok) setPreview(result.data);
    else setError(result.message);
  }

  async function complete(): Promise<void> {
    const payload = request(selected);
    if (payload === null) return;
    const result = await api.complete(payload);
    if (result.ok) {
      setPreview(result.data);
      setCompleted(true);
    } else setError(result.message);
  }

  return (
    <>
      <p className="eyebrow">Comprobación</p>
      <h1>Conciliar</h1>
      <div className="compact-form surface-solid">
        <label className="field">
          Cuenta
          <select
            value={account}
            onChange={(event) => setAccount(event.target.value)}
          >
            {accounts.length === 0 ? (
              <option value="">Sin cuentas conciliables</option>
            ) : null}
            {accounts.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Fecha de corte
          <input
            type="date"
            value={cutoff}
            onChange={(event) => setCutoff(event.target.value)}
          />
        </label>
        <label className="field">
          Saldo real
          <input
            inputMode="decimal"
            value={actual}
            onChange={(event) => setActual(event.target.value)}
          />
        </label>
        <button type="button" onClick={() => void review()}>
          Revisar movimientos
        </button>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {candidates ? (
        <ReconciliationEntryList
          candidates={candidates}
          selected={selected}
          onChange={(id, checked) => void select(id, checked)}
        />
      ) : null}
      {preview ? (
        <>
          <ReconciliationSummary preview={preview} />
          <button
            type="button"
            disabled={preview.difference_cents !== 0}
            onClick={() => void complete()}
          >
            Completar conciliación
          </button>
        </>
      ) : null}
      {completed ? <p role="status">Conciliación completada</p> : null}
    </>
  );
}
