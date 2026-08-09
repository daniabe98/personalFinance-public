export interface AuditEvent {
  readonly id: string;
  readonly occurred_at: string;
  readonly action: string;
  readonly result: string;
  readonly actor_id: string | null;
  readonly entity_type: string;
  readonly entity_id: string;
  readonly correlation_id: string;
}

const ACTION_LABELS: Readonly<Record<string, string>> = {
  POSTING: "Se contabilizó un movimiento.",
  RECONCILIATION_COMPLETED: "Se completó una conciliación.",
};

export function AuditList({
  events,
  hasMore,
  onLoadMore,
}: {
  readonly events: readonly AuditEvent[];
  readonly hasMore: boolean;
  readonly onLoadMore: () => void;
}): React.JSX.Element {
  return (
    <section aria-labelledby="audit-heading">
      <h2 id="audit-heading">Actividad de seguridad</h2>
      {events.length === 0 ? (
        <p role="status">Sin actividad registrada</p>
      ) : (
        <ul className="history-list">
          {events.map((event) => (
            <li className="history-row surface-solid" key={event.id}>
              <strong>
                {ACTION_LABELS[event.action] ?? "Se registró una actividad."}
              </strong>
              <time dateTime={event.occurred_at}>{event.occurred_at}</time>
              <span>
                Resultado: {event.result === "SUCCESS" ? "Correcto" : "Fallido"}
              </span>
              <span>Referencia: {event.correlation_id}</span>
            </li>
          ))}
        </ul>
      )}
      {hasMore ? (
        <button type="button" onClick={onLoadMore}>
          Cargar más
        </button>
      ) : null}
    </section>
  );
}
