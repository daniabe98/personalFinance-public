import { useEffect, useRef, useState } from "react";

import { ErrorMessage } from "../../ui/feedback";
import { localCalendarDate } from "../../lib/local-date";
import { createIdempotencyKey } from "../../lib/idempotency-key";
import type { TransactionsApi } from "./api";

export function ReversalDialog({
  api,
  transactionId,
  onClose,
  onComplete,
}: {
  readonly api: TransactionsApi;
  readonly transactionId: string;
  readonly onClose: () => void;
  readonly onComplete: () => void;
}): React.JSX.Element {
  const dialog = useRef<HTMLDialogElement>(null);
  const today = localCalendarDate();
  const [economicDate, setEconomicDate] = useState(today);
  const [cashDate, setCashDate] = useState(today);
  const [key] = useState(createIdempotencyKey);
  const [error, setError] = useState(false);
  useEffect(() => {
    const element = dialog.current;
    if (element === null) return;
    if (typeof element.showModal === "function") element.showModal();
    else element.setAttribute("open", "");
  }, []);
  async function confirm(): Promise<void> {
    const result = await api.reverse(
      transactionId,
      {
        economic_date: economicDate,
        cash_date: cashDate,
      },
      key,
    );
    if (!result.ok) {
      setError(true);
      return;
    }
    onComplete();
  }
  return (
    <dialog className="glass-strong" ref={dialog} onCancel={onClose}>
      <h2>Anular con un movimiento compensatorio</h2>
      <p>
        El movimiento original seguirá visible. Se añadirá otro que compense su
        efecto.
      </p>
      <p>
        La descripción se generará automáticamente a partir del movimiento
        original.
      </p>
      {error ? (
        <ErrorMessage>
          No se guardó ningún movimiento. Inténtalo de nuevo.
        </ErrorMessage>
      ) : null}
      <div className="field">
        <label htmlFor="reversal-economic-date">Fecha del cambio</label>
        <input
          id="reversal-economic-date"
          type="date"
          value={economicDate}
          onChange={(event) => setEconomicDate(event.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="reversal-cash-date">Fecha en la cuenta</label>
        <input
          id="reversal-cash-date"
          type="date"
          value={cashDate}
          onChange={(event) => setCashDate(event.target.value)}
        />
      </div>
      <div className="actions">
        <button type="button" onClick={() => void confirm()}>
          Confirmar compensación
        </button>
        <button className="secondary" type="button" onClick={onClose}>
          Cancelar
        </button>
      </div>
    </dialog>
  );
}
