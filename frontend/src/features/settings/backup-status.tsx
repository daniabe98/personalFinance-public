type BackupState = "NEVER_RUN" | "PENDING" | "VERIFIED" | "FAILED";
type VerificationResult = "NOT_AVAILABLE" | "PENDING" | "PASSED" | "FAILED";

export interface BackupStatusData {
  readonly state: BackupState;
  readonly last_valid_backup_date: string | null;
  readonly last_verification_failure_date: string | null;
  readonly verification_result: VerificationResult;
  readonly domestic_date: string;
  readonly retention_count: number;
}

interface StatePresentation {
  readonly title: string;
  readonly explanation: string;
}

const STATE_PRESENTATION: Readonly<Record<BackupState, StatePresentation>> = {
  NEVER_RUN: {
    title: "Sin ejecutar",
    explanation: "Todavía no se ha ejecutado ninguna copia de seguridad.",
  },
  PENDING: {
    title: "Pendiente de verificación",
    explanation: "La copia más reciente está esperando verificación.",
  },
  VERIFIED: {
    title: "Copia verificada",
    explanation: "La copia más reciente se verificó correctamente.",
  },
  FAILED: {
    title: "Verificación fallida",
    explanation: "La copia más reciente no superó la verificación.",
  },
};

const VERIFICATION_LABEL: Readonly<Record<VerificationResult, string>> = {
  NOT_AVAILABLE: "No disponible",
  PENDING: "Pendiente",
  PASSED: "Correcta",
  FAILED: "Fallida",
};

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

function retentionLabel(count: number): string {
  return `${count} ${count === 1 ? "copia" : "copias"}`;
}

function StatusIcon({
  state,
  label,
}: {
  readonly state: BackupState;
  readonly label: string;
}): React.JSX.Element {
  return (
    <svg
      aria-label={`Estado de la copia: ${label}`}
      className="backup-status-icon"
      role="img"
      viewBox="0 0 48 48"
    >
      <circle
        cx="24"
        cy="24"
        r="20"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
      />
      {state === "VERIFIED" ? (
        <path
          d="m15 24 6 6 13-14"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
      ) : null}
      {state === "FAILED" ? (
        <>
          <path
            d="M24 14v14"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="3"
          />
          <circle cx="24" cy="34" r="2" fill="currentColor" />
        </>
      ) : null}
      {state === "PENDING" ? (
        <path
          d="M24 14v11l7 4"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
      ) : null}
      {state === "NEVER_RUN" ? (
        <path
          d="M16 24h16"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="3"
        />
      ) : null}
    </svg>
  );
}

export function BackupStatus({
  status,
}: {
  readonly status: BackupStatusData;
}): React.JSX.Element {
  const presentation = STATE_PRESENTATION[status.state];

  return (
    <section
      aria-labelledby="backup-heading"
      className="backup-surface surface-solid"
      data-backup-state={status.state}
    >
      <h2 id="backup-heading">Copias de seguridad</h2>
      <header className="backup-header">
        <StatusIcon state={status.state} label={presentation.title} />
        <div className="backup-status-copy">
          <p className="eyebrow">Estado actual</p>
          <h3>{presentation.title}</h3>
          <p>{presentation.explanation}</p>
        </div>
      </header>
      <dl className="backup-milestones">
        <div className="backup-milestone">
          <dt>Última copia válida</dt>
          <dd>
            {status.last_valid_backup_date
              ? formatDate(status.last_valid_backup_date)
              : "Todavía no hay copia válida"}
          </dd>
        </div>
        <div className="backup-milestone">
          <dt>Verificación</dt>
          <dd>{VERIFICATION_LABEL[status.verification_result]}</dd>
        </div>
        <div className="backup-milestone">
          <dt>Retención</dt>
          <dd>{retentionLabel(status.retention_count)}</dd>
        </div>
        <div className="backup-milestone">
          <dt>Próxima ejecución</dt>
          <dd>{tomorrow(status.domestic_date)}</dd>
        </div>
      </dl>
      {status.last_verification_failure_date ? (
        <p className="backup-failure" role="status">
          La verificación falló el{" "}
          {formatDate(status.last_verification_failure_date)}.
        </p>
      ) : null}
      <a className="backup-runbook" href="/docs/runbooks/backup-restore">
        Abrir guía de recuperación
      </a>
    </section>
  );
}
