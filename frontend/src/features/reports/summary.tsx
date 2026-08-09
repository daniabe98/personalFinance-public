import { useCallback, useEffect, useState } from "react";

import { CashReportView, type CashReport } from "./cash";
import { EconomicReportView, type EconomicReport } from "./economic";
import { NetWorthReportView, type NetWorthReport } from "./net-worth";

type Result<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly message: string };

export interface ReportsApi {
  economic(start: string, end: string): Promise<Result<EconomicReport>>;
  cash(start: string, end: string): Promise<Result<CashReport>>;
  netWorth(asOf: string): Promise<Result<NetWorthReport>>;
}

export function ReportsSummary({
  api,
  initialInterval,
  autoLoad = true,
}: {
  readonly api: ReportsApi;
  readonly initialInterval: {
    readonly startDate: string;
    readonly endDate: string;
  };
  readonly autoLoad?: boolean;
}): React.JSX.Element {
  const [start, setStart] = useState(initialInterval.startDate);
  const [end, setEnd] = useState(initialInterval.endDate);
  const [economic, setEconomic] = useState<EconomicReport>();
  const [cash, setCash] = useState<CashReport>();
  const [worth, setWorth] = useState<NetWorthReport>();
  const [error, setError] = useState(false);

  const load = useCallback(
    async (from: string, to: string): Promise<void> => {
      setError(false);
      const [economicResult, cashResult, worthResult] = await Promise.all([
        api.economic(from, to),
        api.cash(from, to),
        api.netWorth(to),
      ]);
      if (!economicResult.ok || !cashResult.ok || !worthResult.ok) {
        setError(true);
        return;
      }
      setEconomic(economicResult.data);
      setCash(cashResult.data);
      setWorth(worthResult.data);
    },
    [api],
  );

  useEffect(() => {
    if (autoLoad) {
      void load(initialInterval.startDate, initialInterval.endDate);
    }
  }, [autoLoad, initialInterval.endDate, initialInterval.startDate, load]);

  return (
    <>
      <p className="eyebrow">Vista general</p>
      <h1>Resumen</h1>
      <p>Tu situación doméstica, reunida en un solo lugar.</p>
      <form
        className="form-grid surface-solid"
        onSubmit={(event) => {
          event.preventDefault();
          void load(start, end);
        }}
      >
        <label className="field">
          Desde
          <input
            type="date"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />
        </label>
        <label className="field">
          Hasta
          <input
            type="date"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
          />
        </label>
        <button type="submit">Actualizar</button>
      </form>
      {error ? <p role="alert">No se pudieron cargar los informes.</p> : null}
      <div className="reports-grid" aria-live="polite">
        {economic ? <EconomicReportView report={economic} /> : null}
        {cash ? <CashReportView report={cash} /> : null}
        {worth ? <NetWorthReportView report={worth} /> : null}
      </div>
    </>
  );
}
