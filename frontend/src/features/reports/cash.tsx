import { formatEurCents } from "../../lib/money";
import { CompositionChart } from "./composition-chart";

export interface CashReport {
  readonly receipts_cents: number;
  readonly payments_cents: number;
  readonly net_cash_flow_cents: number;
}

export function CashReportView({
  report,
}: {
  readonly report: CashReport;
}): React.JSX.Element {
  return (
    <section aria-labelledby="cash-heading">
      <h2 id="cash-heading">Dinero disponible</h2>
      <dl className="report-totals">
        <div>
          <dt>Cobros</dt>
          <dd className="money">{formatEurCents(report.receipts_cents)}</dd>
        </div>
        <div>
          <dt>Pagos</dt>
          <dd className="money">{formatEurCents(report.payments_cents)}</dd>
        </div>
        <div>
          <dt>Cambio neto</dt>
          <dd className="money">
            {formatEurCents(report.net_cash_flow_cents)}
          </dd>
        </div>
      </dl>
      <CompositionChart
        title="Composición actual de Cobros y Pagos"
        first={{ label: "Cobros", valueCents: report.receipts_cents }}
        second={{ label: "Pagos", valueCents: report.payments_cents }}
      />
    </section>
  );
}
