import type { TransactionStatus } from "../../api/schema";
import { Icon } from "../../ui/icons";

const labels: Readonly<Record<TransactionStatus, string>> = {
  DRAFT: "Borrador",
  POSTED: "Contabilizado",
  RECONCILED: "Comprobado",
  VOIDED: "Anulado",
};

export function StatusBadge({
  status,
}: {
  readonly status: TransactionStatus;
}): React.JSX.Element {
  const icon =
    status === "DRAFT"
      ? "draft"
      : status === "VOIDED"
        ? "void"
        : status === "RECONCILED"
          ? "reconcile"
          : "check";
  return (
    <span
      aria-label={`Estado: ${labels[status]}`}
      className={`status status-${status.toLowerCase()}`}
      role="status"
    >
      <Icon name={icon} />
      {labels[status]}
    </span>
  );
}
