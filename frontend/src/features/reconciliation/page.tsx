import { useEffect, useRef, useState } from "react";

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

function requestKey(request: ReconciliationRequest): string {
  return JSON.stringify(request);
}

function createRequest(
  account: string,
  cutoff: string,
  hasCutoffDate: boolean,
  actualBalanceCents: number | null,
  ids: ReadonlySet<string>,
): ReconciliationRequest | null {
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
  const [previewRequestKey, setPreviewRequestKey] = useState("");
  const [accountError, setAccountError] = useState("");
  const [candidateError, setCandidateError] = useState("");
  const [previewError, setPreviewError] = useState("");
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);
  const [completed, setCompleted] = useState(false);
  const requestVersion = useRef(0);
  const completionInFlight = useRef(false);
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
    const payload = createRequest(
      account,
      cutoff,
      hasCutoffDate,
      actualBalanceCents,
      selected,
    );
    if (payload === null || selected.size === 0) {
      setIsPreviewLoading(false);
      setPreview(undefined);
      setPreviewRequestKey("");
      return;
    }

    setIsPreviewLoading(true);
    void api.preview(payload).then((result) => {
      if (!active) return;
      setIsPreviewLoading(false);
      if (result.ok) {
        setPreview(result.data);
        setPreviewRequestKey(requestKey(payload));
      } else {
        setPreview(undefined);
        setPreviewRequestKey("");
        setPreviewError(result.message);
      }
    });
    return () => {
      active = false;
    };
  }, [account, actualBalanceCents, api, cutoff, hasCutoffDate, selected]);

  function select(entryId: string, checked: boolean): void {
    invalidateCurrentRequest();
    const next = new Set(selected);
    if (checked) next.add(entryId);
    else next.delete(entryId);
    setSelected(next);
  }

  function invalidateCurrentRequest(): void {
    requestVersion.current += 1;
    setCompleted(false);
  }

  async function complete(): Promise<void> {
    const payload = createRequest(
      account,
      cutoff,
      hasCutoffDate,
      actualBalanceCents,
      selected,
    );
    if (
      payload === null ||
      selected.size === 0 ||
      preview === undefined ||
      preview.difference_cents !== 0 ||
      previewRequestKey !== requestKey(payload) ||
      isPreviewLoading ||
      isCompleting ||
      completionInFlight.current
    ) {
      return;
    }

    const version = requestVersion.current;
    const snapshotKey = requestKey(payload);
    completionInFlight.current = true;
    setIsCompleting(true);
    setPreviewError("");
    try {
      const result = await api.complete(payload);
      if (version !== requestVersion.current) return;
      if (result.ok) {
        setPreview(result.data);
        setPreviewRequestKey(snapshotKey);
        setCompleted(true);
      } else {
        setPreviewError(result.message);
      }
    } finally {
      completionInFlight.current = false;
      setIsCompleting(false);
    }
  }

  const currentRequest = createRequest(
    account,
    cutoff,
    hasCutoffDate,
    actualBalanceCents,
    selected,
  );
  const hasCurrentPreview =
    currentRequest !== null &&
    selected.size > 0 &&
    previewRequestKey === requestKey(currentRequest);

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
              invalidateCurrentRequest();
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
              invalidateCurrentRequest();
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
            onChange={(event) => {
              invalidateCurrentRequest();
              setActual(event.target.value);
            }}
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
          disabled={
            !hasCurrentPreview ||
            preview.difference_cents !== 0 ||
            isPreviewLoading ||
            isCompleting
          }
          onClick={() => void complete()}
        >
          Completar conciliación
        </button>
      ) : null}
      {completed ? <p role="status">Conciliación completada</p> : null}
    </>
  );
}
