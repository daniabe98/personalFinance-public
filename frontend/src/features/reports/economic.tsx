import { formatEurCents } from "../../lib/money";

const economicDateFormatter = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

function formatEconomicDate(isoDate: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (match === null) {
    return isoDate;
  }

  const [, yearText, monthText, dayText] = match;
  if (
    yearText === undefined ||
    monthText === undefined ||
    dayText === undefined
  ) {
    return isoDate;
  }

  const date = new Date(
    Date.UTC(
      Number.parseInt(yearText, 10),
      Number.parseInt(monthText, 10) - 1,
      Number.parseInt(dayText, 10),
    ),
  );
  return economicDateFormatter.format(date).replaceAll(".", "");
}

function formatSignedEurCents(amountCents: number): string {
  if (amountCents > 0) {
    return `+${formatEurCents(amountCents)}`;
  }
  if (amountCents < 0) {
    return `−${formatEurCents(Math.abs(amountCents))}`;
  }
  return formatEurCents(amountCents);
}

function getContributionPresentation(amountCents: number): {
  readonly modifier: "movement" | "neutral";
} {
  if (amountCents === 0) {
    return { modifier: "neutral" };
  }
  return { modifier: "movement" };
}

export interface Contribution {
  readonly transaction_id: string;
  readonly amount_cents: number;
  readonly economic_date: string;
  readonly description: string | null;
}

export interface EconomicReport {
  readonly income_cents: number;
  readonly expense_cents: number;
  readonly result_cents: number;
  readonly contributions: readonly Contribution[];
}

export function EconomicReportView({
  report,
  onViewDetail,
}: {
  readonly report: EconomicReport;
  readonly onViewDetail?: (
    transactionId: string,
    opener: HTMLButtonElement,
  ) => void;
}): React.JSX.Element {
  const empty =
    report.income_cents === 0 &&
    report.expense_cents === 0 &&
    report.result_cents === 0 &&
    report.contributions.length === 0;
  return (
    <section className="activity-report" aria-labelledby="economic-heading">
      <h2 id="economic-heading">Actividad del periodo</h2>
      {empty ? <p role="status">Sin actividad económica</p> : null}
      <dl className="activity-totals">
        <div className="activity-total">
          <dt>Ingresos</dt>
          <dd className="money">{formatEurCents(report.income_cents)}</dd>
        </div>
        <div className="activity-total">
          <dt>Gastos</dt>
          <dd className="money">{formatEurCents(report.expense_cents)}</dd>
        </div>
        <div className="activity-total activity-total--result">
          <dt>Resultado</dt>
          <dd className="money">{formatEurCents(report.result_cents)}</dd>
        </div>
      </dl>
      <ul className="activity-list">
        {report.contributions.map((item, index) => {
          const date = formatEconomicDate(item.economic_date);
          const signedAmount = formatSignedEurCents(item.amount_cents);
          const presentation = getContributionPresentation(item.amount_cents);
          const description = item.description ?? "Sin descripción";

          return (
            <li
              className={`activity-item activity-item--${presentation.modifier}`}
              key={`${item.transaction_id}-${item.economic_date}`}
            >
              <div className="activity-context">
                <time className="activity-date" dateTime={item.economic_date}>
                  {date}
                </time>
                <strong className="activity-description">{description}</strong>
                {item.amount_cents === 0 ? (
                  <span className="activity-type activity-type--neutral">
                    Sin impacto
                  </span>
                ) : null}
              </div>
              <span className="activity-amount money">{signedAmount}</span>
              <button
                type="button"
                className="activity-action"
                aria-label={`Ver detalle de ${description}, ${signedAmount}, ${date}, ${index + 1} de ${report.contributions.length}`}
                onClick={(event) =>
                  onViewDetail?.(item.transaction_id, event.currentTarget)
                }
              >
                Ver detalle
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
