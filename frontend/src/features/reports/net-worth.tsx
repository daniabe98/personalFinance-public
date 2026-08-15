import { formatEurCents } from "../../lib/money";
import { CompositionChart } from "./composition-chart";

export interface NetWorthReport {
  readonly assets_cents: number;
  readonly liabilities_cents: number;
  readonly net_worth_cents: number;
}

export function NetWorthReportView({
  report,
}: {
  readonly report: NetWorthReport;
}): React.JSX.Element {
  return (
    <section aria-labelledby="worth-heading">
      <h2 id="worth-heading">Patrimonio</h2>
      <dl className="report-totals">
        <div>
          <dt>Activos</dt>
          <dd className="money">{formatEurCents(report.assets_cents)}</dd>
        </div>
        <div>
          <dt>Compromisos</dt>
          <dd className="money">{formatEurCents(report.liabilities_cents)}</dd>
        </div>
        <div>
          <dt>Patrimonio neto</dt>
          <dd className="money">{formatEurCents(report.net_worth_cents)}</dd>
        </div>
      </dl>
      <CompositionChart
        title="Composición actual de Activos y Compromisos"
        first={{ label: "Activos", valueCents: report.assets_cents }}
        second={{
          label: "Compromisos",
          valueCents: report.liabilities_cents,
        }}
      />
    </section>
  );
}
