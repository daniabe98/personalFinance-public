export interface BackupStatusData {
  readonly state: string;
  readonly last_valid_backup_date: string | null;
  readonly last_verification_failure_date: string | null;
  readonly verification_result: string;
  readonly domestic_date: string;
  readonly retention_count: number;
}

const dateFormatter = new Intl.DateTimeFormat("es-ES", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

function formatDate(value: string): string {
  return dateFormatter.format(new Date(`${value}T00:00:00Z`));
}

function tomorrow(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return dateFormatter.format(date);
}

export function BackupStatus({
  status,
}: {
  readonly status: BackupStatusData;
}): React.JSX.Element {
  return (
    <section aria-labelledby="backup-heading">
      <h2 id="backup-heading">Copias de seguridad</h2>
      <dl className="report-totals">
        <div>
          <dt>Última copia válida</dt>
          <dd>
            {status.last_valid_backup_date
              ? formatDate(status.last_valid_backup_date)
              : "Todavía no hay copia válida"}
          </dd>
        </div>
        <div>
          <dt>Última verificación</dt>
          <dd>
            {status.verification_result === "FAILED"
              ? `Fallida`
              : status.verification_result === "NOT_RUN"
                ? "Pendiente"
                : "Correcta"}
          </dd>
        </div>
        <div>
          <dt>Retención</dt>
          <dd>{status.retention_count} copias</dd>
        </div>
        <div>
          <dt>Próxima copia esperada</dt>
          <dd>{tomorrow(status.domestic_date)}</dd>
        </div>
      </dl>
      {status.last_verification_failure_date ? (
        <p role="status">
          La verificación falló el{" "}
          {formatDate(status.last_verification_failure_date)}.
        </p>
      ) : null}
      <a href="/docs/runbooks/backup-restore">Abrir guía de recuperación</a>
    </section>
  );
}
