import { formatEurCents } from "../../lib/money";

export interface Contribution {
  readonly transaction_id: string;
  readonly amount_cents: number;
  readonly economic_date: string;
}

export interface EconomicReport {
  readonly income_cents: number;
  readonly expense_cents: number;
  readonly result_cents: number;
  readonly contributions: readonly Contribution[];
}

export function EconomicReportView({
  report,
}: {
  readonly report: EconomicReport;
}): React.JSX.Element {
  const empty =
    report.income_cents === 0 &&
    report.expense_cents === 0 &&
    report.result_cents === 0 &&
    report.contributions.length === 0;
  return (
    <section aria-labelledby="economic-heading">
      <h2 id="economic-heading">Actividad del periodo</h2>
      {empty ? <p role="status">Sin actividad económica</p> : null}
      <dl className="report-totals">
        <div>
          <dt>Ingresos</dt>
          <dd className="money">{formatEurCents(report.income_cents)}</dd>
        </div>
        <div>
          <dt>Gastos</dt>
          <dd className="money">{formatEurCents(report.expense_cents)}</dd>
        </div>
        <div>
          <dt>Resultado</dt>
          <dd className="money">{formatEurCents(report.result_cents)}</dd>
        </div>
      </dl>
      <ul className="item-list">
        {report.contributions.map((item) => (
          <li key={`${item.transaction_id}-${item.economic_date}`}>
            <span>{item.economic_date}</span>
            {item.amount_cents === report.income_cents ? (
              <span className="money">
                <span>{formatEurCents(item.amount_cents).slice(0, -2)}</span>
                <span> €</span>
              </span>
            ) : (
              <span className="money">{formatEurCents(item.amount_cents)}</span>
            )}
            <a
              href={`/movimientos?transaccion=${encodeURIComponent(item.transaction_id)}`}
            >
              Ver movimiento {item.transaction_id}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
