import { formatEurCents } from "../../lib/money";

export interface ReconciliationPreview {
  readonly actual_balance_cents: number;
  readonly checked_balance_cents: number;
  readonly difference_cents: number;
  readonly currency: "EUR";
}

export function ReconciliationSummary({
  preview,
}: {
  readonly preview: ReconciliationPreview;
}): React.JSX.Element {
  return (
    <section
      className="surface-solid movement-summary"
      aria-labelledby="review"
    >
      <h2 id="review">Revisión</h2>
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
            <span>
              {formatEurCents(preview.checked_balance_cents).slice(0, -2)}
            </span>
            <span> €</span>
          </dd>
        </div>
        <div>
          <dt>Diferencia</dt>
          <dd className="money">{formatEurCents(preview.difference_cents)}</dd>
        </div>
      </dl>
      <p aria-live="polite">
        {preview.difference_cents === 0
          ? "La diferencia es cero."
          : `Quedan ${formatEurCents(preview.difference_cents)} por comprobar.`}
      </p>
    </section>
  );
}
