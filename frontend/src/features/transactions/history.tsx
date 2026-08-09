import type {
  AccountResponse,
  CategoryResponse,
  TransactionResponse,
} from "../../api/schema";
import { formatEurCents } from "../../lib/money";
import { EmptyState } from "../../ui/feedback";
import type { TransactionsApi } from "./api";
import { StatusBadge } from "./status-badge";

export function TransactionHistory({
  accounts = [],
  api,
  categories = [],
  items,
  onChange,
  onEdit,
  onReverse,
}: {
  readonly accounts?: readonly AccountResponse[];
  readonly api: TransactionsApi;
  readonly categories?: readonly CategoryResponse[];
  readonly items: readonly TransactionResponse[];
  readonly onChange: () => void;
  readonly onEdit: (item: TransactionResponse) => void;
  readonly onReverse: (item: TransactionResponse) => void;
}): React.JSX.Element {
  if (items.length === 0)
    return (
      <EmptyState title="Sin movimientos">
        Todavía no has guardado movimientos.
      </EmptyState>
    );
  return (
    <ol className="history-list">
      {items.map((item) => {
        const account = accounts.find(
          (candidate) => candidate.id === item.account_id,
        );
        const destination = accounts.find(
          (candidate) => candidate.id === item.destination_account_id,
        );
        const category = categories.find(
          (candidate) => candidate.id === item.category_id,
        );
        return (
          <li
            className="surface-solid history-row"
            id={relationshipTarget(item.id)}
            key={item.id}
          >
            <div>
              <strong>{item.description ?? "Sin descripción"}</strong>
              <StatusBadge status={item.status} />
            </div>
            <span className="money">
              {item.amount_cents === null
                ? "Importe no disponible"
                : formatEurCents(item.amount_cents)}
            </span>
            <dl>
              <div>
                <dt>Fecha económica</dt>
                <dd>{item.economic_date}</dd>
              </div>
              {item.cash_date ? (
                <div>
                  <dt>Fecha en la cuenta</dt>
                  <dd>{item.cash_date}</dd>
                </div>
              ) : null}
              {account ? (
                <div>
                  <dt>
                    {item.kind === "TRANSFER" ? "Cuenta de origen" : "Cuenta"}
                  </dt>
                  <dd>
                    {account.name}
                    {account.is_archived ? " (archivada)" : ""}
                  </dd>
                </div>
              ) : null}
              {destination ? (
                <div>
                  <dt>Cuenta de destino</dt>
                  <dd>
                    {destination.name}
                    {destination.is_archived ? " (archivada)" : ""}
                  </dd>
                </div>
              ) : null}
              {category ? (
                <div>
                  <dt>Categoría</dt>
                  <dd>
                    {category.name}
                    {category.is_archived ? " (archivada)" : ""}
                  </dd>
                </div>
              ) : null}
            </dl>
            {item.original_transaction_id ? (
              <RelationshipLink
                id={item.original_transaction_id}
                label="Movimiento original"
              />
            ) : null}
            {item.reversal_transaction_id ? (
              <RelationshipLink
                id={item.reversal_transaction_id}
                label="Movimiento compensatorio"
              />
            ) : null}
            {item.corrected_original_transaction_id ? (
              <RelationshipLink
                id={item.corrected_original_transaction_id}
                label="Corrige el movimiento"
              />
            ) : null}
            {item.replacement_transaction_id ? (
              <RelationshipLink
                id={item.replacement_transaction_id}
                label="Borrador de corrección"
              />
            ) : null}
            <div className="actions">
              {item.status === "DRAFT" ? (
                <>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => onEdit(item)}
                  >
                    Editar borrador
                  </button>
                  <button
                    className="danger"
                    type="button"
                    onClick={() =>
                      void api.discardDraft(item.id).then(onChange)
                    }
                  >
                    Descartar borrador
                  </button>
                </>
              ) : null}
              {item.status === "POSTED" || item.status === "RECONCILED" ? (
                <button
                  className="secondary"
                  type="button"
                  onClick={() => onReverse(item)}
                >
                  Anular con un movimiento compensatorio
                </button>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function relationshipTarget(id: string): string {
  return `movement-${encodeURIComponent(id)}`;
}

function RelationshipLink({
  id,
  label,
}: {
  readonly id: string;
  readonly label: string;
}): React.JSX.Element {
  return (
    <p>
      {label}: <a href={`#${relationshipTarget(id)}`}>{id}</a>
    </p>
  );
}
