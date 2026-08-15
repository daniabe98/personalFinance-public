import { useEffect, useId, useRef, useState } from "react";

import { formatEurCents } from "../../lib/money";

type Result<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly message: string };

export interface MovementDetail {
  readonly id: string;
  readonly kind: "OPENING" | "INCOME" | "EXPENSE" | "TRANSFER" | "REVERSAL";
  readonly status: "DRAFT" | "POSTED" | "RECONCILED" | "VOIDED";
  readonly status_label: string;
  readonly economic_date: string;
  readonly cash_date: string | null;
  readonly description: string | null;
  readonly amount_cents?: number | null;
  readonly account_id?: string | null;
  readonly category_id?: string | null;
  readonly destination_account_id?: string | null;
  readonly original_transaction_id?: string | null;
  readonly reversal_transaction_id?: string | null;
  readonly corrected_original_transaction_id?: string | null;
  readonly replacement_transaction_id?: string | null;
}

export interface DetailCatalogItem {
  readonly id: string;
  readonly name: string;
  readonly is_archived: boolean;
}

export interface MovementDetailApi {
  transaction(transactionId: string): Promise<Result<MovementDetail | null>>;
  accounts(): Promise<Result<readonly DetailCatalogItem[]>>;
  categories(): Promise<Result<readonly DetailCatalogItem[]>>;
}

type DetailState =
  | { readonly state: "loading" }
  | { readonly state: "error"; readonly message: string }
  | { readonly state: "missing" }
  | {
      readonly state: "ready";
      readonly detail: MovementDetail;
      readonly accounts: ReadonlyMap<string, string>;
      readonly categories: ReadonlyMap<string, string>;
    };

const DETAIL_KIND_LABELS: Readonly<Record<MovementDetail["kind"], string>> = {
  OPENING: "Apertura",
  INCOME: "Ingreso",
  EXPENSE: "Gasto",
  TRANSFER: "Transferencia",
  REVERSAL: "Anulación",
};

const detailDateFormatter = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

function formatDetailDate(isoDate: string): string {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (parts === null) return isoDate;
  const [, year, month, day] = parts;
  if (year === undefined || month === undefined || day === undefined) {
    return isoDate;
  }
  return detailDateFormatter
    .format(
      new Date(
        Date.UTC(
          Number.parseInt(year, 10),
          Number.parseInt(month, 10) - 1,
          Number.parseInt(day, 10),
        ),
      ),
    )
    .replaceAll(".", "");
}

function formatSignedAmount(amountCents: number | null | undefined): string {
  if (amountCents === null || amountCents === undefined) return "No disponible";
  if (amountCents > 0) return `+${formatEurCents(amountCents)}`;
  if (amountCents < 0) return `−${formatEurCents(Math.abs(amountCents))}`;
  return formatEurCents(0);
}

function resolveCatalogName(
  id: string | null | undefined,
  names: ReadonlyMap<string, string>,
): string {
  if (id === null) return "No aplica";
  if (id === undefined) return "No disponible";
  return names.get(id) ?? "No disponible";
}

function catalogMap(
  result: Result<readonly DetailCatalogItem[]>,
): ReadonlyMap<string, string> {
  if (!result.ok) return new Map();
  return new Map(result.data.map((item) => [item.id, item.name]));
}

function RelationList({ detail }: { readonly detail: MovementDetail }) {
  const relations = [
    [detail.original_transaction_id, "Movimiento original relacionado"],
    [detail.reversal_transaction_id, "Movimiento compensatorio relacionado"],
    [
      detail.corrected_original_transaction_id,
      "Movimiento corregido relacionado",
    ],
    [detail.replacement_transaction_id, "Movimiento de reemplazo relacionado"],
  ].filter(
    (relation): relation is [string, string] => typeof relation[0] === "string",
  );

  if (relations.length === 0) {
    return <p>Sin movimientos relacionados.</p>;
  }
  return (
    <ul>
      {relations.map(([, label]) => (
        <li key={label}>{label}</li>
      ))}
    </ul>
  );
}

export function MovementDetailDialog({
  transactionId,
  api,
  onClose,
}: {
  readonly transactionId: string;
  readonly api: MovementDetailApi;
  readonly onClose: () => void;
}): React.JSX.Element {
  const headingId = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [detailState, setDetailState] = useState<DetailState>({
    state: "loading",
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog === null) return;
    if (typeof dialog.showModal === "function") {
      if (!dialog.open) dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
    closeButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    let isCurrent = true;
    setDetailState({ state: "loading" });
    void Promise.all([
      api.transaction(transactionId),
      api.accounts(),
      api.categories(),
    ]).then(([transactionResult, accountResult, categoryResult]) => {
      if (!isCurrent) return;
      if (!transactionResult.ok) {
        setDetailState({
          state: "error",
          message: transactionResult.message,
        });
        return;
      }
      if (transactionResult.data === null) {
        setDetailState({ state: "missing" });
        return;
      }
      setDetailState({
        state: "ready",
        detail: transactionResult.data,
        accounts: catalogMap(accountResult),
        categories: catalogMap(categoryResult),
      });
    });
    return () => {
      isCurrent = false;
    };
  }, [api, transactionId]);

  function requestClose(): void {
    const dialog = dialogRef.current;
    if (dialog !== null && typeof dialog.close === "function") {
      dialog.close();
      return;
    }
    dialog?.removeAttribute("open");
    onClose();
  }

  const heading =
    detailState.state === "ready"
      ? (detailState.detail.description ?? "Sin descripción")
      : "Detalle del movimiento";

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={headingId}
      className="movement-detail-dialog glass-strong"
      onCancel={(event) => {
        event.preventDefault();
        requestClose();
      }}
      onClose={onClose}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          requestClose();
          return;
        }
        if (event.key !== "Tab") return;
        const dialog = dialogRef.current;
        if (dialog === null) return;
        const focusable = Array.from(
          dialog.querySelectorAll<HTMLElement>(
            'button:not([disabled]), a[href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
          ),
        );
        const first = focusable.at(0);
        const last = focusable.at(-1);
        if (first === undefined || last === undefined) return;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }}
    >
      <header>
        <p className="eyebrow">Detalle del movimiento</p>
        <h2 id={headingId}>{heading}</h2>
      </header>
      {detailState.state === "loading" ? (
        <p role="status">Cargando detalle…</p>
      ) : null}
      {detailState.state === "error" ? (
        <p role="alert">{detailState.message}</p>
      ) : null}
      {detailState.state === "missing" ? (
        <p role="status">El movimiento ya no está disponible.</p>
      ) : null}
      {detailState.state === "ready" ? (
        <>
          <p className="money movement-detail-amount">
            {formatSignedAmount(detailState.detail.amount_cents)}
          </p>
          <dl className="movement-detail-fields">
            <div>
              <dt>Tipo</dt>
              <dd>{DETAIL_KIND_LABELS[detailState.detail.kind]}</dd>
            </div>
            <div>
              <dt>Estado</dt>
              <dd>{detailState.detail.status_label}</dd>
            </div>
            <div>
              <dt>Fecha económica</dt>
              <dd>
                <time dateTime={detailState.detail.economic_date}>
                  {formatDetailDate(detailState.detail.economic_date)}
                </time>
              </dd>
            </div>
            <div>
              <dt>Fecha en la cuenta</dt>
              <dd>
                {detailState.detail.cash_date === null ? (
                  "No aplica"
                ) : (
                  <time dateTime={detailState.detail.cash_date}>
                    {formatDetailDate(detailState.detail.cash_date)}
                  </time>
                )}
              </dd>
            </div>
            <div>
              <dt>Cuenta</dt>
              <dd>
                {resolveCatalogName(
                  detailState.detail.account_id,
                  detailState.accounts,
                )}
              </dd>
            </div>
            <div>
              <dt>Cuenta de destino</dt>
              <dd>
                {resolveCatalogName(
                  detailState.detail.destination_account_id,
                  detailState.accounts,
                )}
              </dd>
            </div>
            <div>
              <dt>Categoría</dt>
              <dd>
                {resolveCatalogName(
                  detailState.detail.category_id,
                  detailState.categories,
                )}
              </dd>
            </div>
          </dl>
          <section aria-labelledby={`${headingId}-relations`}>
            <h3 id={`${headingId}-relations`}>Relaciones</h3>
            <RelationList detail={detailState.detail} />
          </section>
        </>
      ) : null}
      <footer>
        <button ref={closeButtonRef} type="button" onClick={requestClose}>
          Cerrar
        </button>
      </footer>
    </dialog>
  );
}
