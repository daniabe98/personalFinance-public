import { formatEurCents } from "../../lib/money";

export interface ReconciliationPreview {
  readonly actual_balance_cents: number;
  readonly checked_balance_cents: number;
  readonly difference_cents: number;
  readonly currency: "EUR";
}

export interface ReconciliationProgress {
  readonly hasAccount: boolean;
  readonly hasCutoffDate: boolean;
  readonly hasActualBalance: boolean;
}

export function ReconciliationSummary({
  preview,
  progress,
  isLoading,
  error,
}: {
  readonly preview: ReconciliationPreview | undefined;
  readonly progress: ReconciliationProgress;
  readonly isLoading: boolean;
  readonly error: string;
}): React.JSX.Element {
  const isIncomplete =
    !progress.hasAccount ||
    !progress.hasCutoffDate ||
    !progress.hasActualBalance;

  return (
    <section
      className="surface-solid movement-summary"
      aria-labelledby="review"
    >
      <h2 id="review">Revisión</h2>
      <ul className="status-list" aria-label="Datos para la revisión">
        <li>{progress.hasAccount ? "Cuenta lista" : "Cuenta pendiente"}</li>
        <li>{progress.hasCutoffDate ? "Fecha lista" : "Fecha pendiente"}</li>
        <li>
          {progress.hasActualBalance
            ? "Saldo real listo"
            : "Saldo real pendiente"}
        </li>
      </ul>
      <div aria-live="polite">
        {error ? (
          <p role="alert">No se pudo calcular la revisión: {error}</p>
        ) : isIncomplete ? (
          <p>Completa los datos pendientes para calcular la revisión.</p>
        ) : null}
        {!error && !isIncomplete && isLoading ? <p>Calculando…</p> : null}
        {!isIncomplete && !isLoading && !error && preview ? (
          <>
            <dl className="report-totals">
              <div>
                <dt>Saldo real</dt>
                <dd className="money">
                  {formatEurCents(preview.actual_balance_cents)}
                </dd>
              </div>
              <div>
                <dt>Saldo comprobado</dt>
                <dd className="money">
                  {formatEurCents(preview.checked_balance_cents)}
                </dd>
              </div>
              <div>
                <dt>Diferencia</dt>
                <dd className="money">
                  {formatEurCents(preview.difference_cents)}
                </dd>
              </div>
            </dl>
            <p className="status">
              {preview.difference_cents === 0 ? (
                <>
                  <span aria-hidden="true">✓ </span>
                  <strong>Cuadrado</strong>: la diferencia es cero.
                </>
              ) : (
                <>
                  <span aria-hidden="true">△ </span>
                  <strong>Con diferencia</strong>: quedan{" "}
                  {formatEurCents(preview.difference_cents)} por comprobar.
                </>
              )}
            </p>
          </>
        ) : null}
      </div>
    </section>
  );
}
