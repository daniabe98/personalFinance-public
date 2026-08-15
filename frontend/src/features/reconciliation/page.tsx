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
  const [accountError, setAccountError] = useState("");
  const [candidateError, setCandidateError] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [completed, setCompleted] = useState(false);
  const parsedActual = parseEurCents(actual);
  const hasCutoffDate = /^\d{4}-\d{2}-\d{2}$/.test(cutoff);
  const actualBalanceCents = parsedActual.ok ? parsedActual.value : null;

  useEffect(() => {
    let active = true;
    setAccountError("");
    void api.accounts().then((result) => {
      if (!active) return;
      if (result.ok) {
        const available = result.data.filter(
          (item) => item.is_reconcilable && !item.is_archived,
        );
        setAccounts(available);
        setAccount((current) => current || available[0]?.id || "");
      } else {
        setAccountError(result.message);
      }
    });
    return () => {
      active = false;
    };
  }, [api]);

  useEffect(() => {
    let active = true;
    setCandidateError("");
    setCandidates(undefined);
    if (account === "" || !hasCutoffDate) return;

    void api.candidates(account, cutoff).then((result) => {
      if (!active) return;
      if (result.ok) setCandidates(result.data);
      else setCandidateError(result.message);
    });
    return () => {
      active = false;
    };
  }, [account, api, cutoff, hasCutoffDate]);

  useEffect(() => {
    let active = true;
    setCompleted(false);
    setPreviewError("");
    setPreview(undefined);
    if (account === "" || !hasCutoffDate || actualBalanceCents === null) {
      setIsPreviewLoading(false);
      return;
    }

    setIsPreviewLoading(true);
    void api
      .preview({
        account_id: account,
        cutoff_date: cutoff,
        actual_balance_cents: actualBalanceCents,
        selected_entry_ids: [...selected],
      })
      .then((result) => {
        if (!active) return;
        setIsPreviewLoading(false);
        if (result.ok) setPreview(result.data);
        else setPreviewError(result.message);
      });
    return () => {
      active = false;
    };
  }, [account, actualBalanceCents, api, cutoff, hasCutoffDate, selected]);

  function request(ids: ReadonlySet<string>): ReconciliationRequest | null {
    if (account === "" || !hasCutoffDate || actualBalanceCents === null) {
      return null;
    }
    return {
      account_id: account,
      cutoff_date: cutoff,
      actual_balance_cents: actualBalanceCents,
      selected_entry_ids: [...ids],
    };
  }

  function select(entryId: string, checked: boolean): void {
    const next = new Set(selected);
    if (checked) next.add(entryId);
    else next.delete(entryId);
    setSelected(next);
  }

  async function complete(): Promise<void> {
    const payload = request(selected);
    if (payload === null) return;
    const result = await api.complete(payload);
    if (result.ok) {
      setPreview(result.data);
      setCompleted(true);
    } else setPreviewError(result.message);
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
            onChange={(event) => {
              setSelected(new Set());
              setAccount(event.target.value);
            }}
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
            onChange={(event) => {
              setSelected(new Set());
              setCutoff(event.target.value);
            }}
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
      </div>
      <ReconciliationSummary
        progress={{
          hasAccount: account !== "",
          hasCutoffDate,
          hasActualBalance: actualBalanceCents !== null,
        }}
        preview={preview}
        isLoading={isPreviewLoading}
        error={accountError || candidateError || previewError}
      />
      {candidates ? (
        <ReconciliationEntryList
          candidates={candidates}
          selected={selected}
          onChange={select}
        />
      ) : null}
      {preview ? (
        <button
          type="button"
          disabled={preview.difference_cents !== 0}
          onClick={() => void complete()}
        >
          Completar conciliación
        </button>
      ) : null}
      {completed ? <p role="status">Conciliación completada</p> : null}
    </>
  );
}
