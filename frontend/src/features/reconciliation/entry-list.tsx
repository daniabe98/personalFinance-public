import { formatEurCents } from "../../lib/money";

export interface ReconciliationCandidate {
  readonly entry_id: string;
  readonly description: string | null;
  readonly effect_cents: number;
  readonly eligibility_date: string;
  readonly kind: string;
}

export function ReconciliationEntryList({
  candidates,
  selected,
  onChange,
}: {
  readonly candidates: readonly ReconciliationCandidate[];
  readonly selected: ReadonlySet<string>;
  readonly onChange: (entryId: string, checked: boolean) => void;
}): React.JSX.Element {
  if (candidates.length === 0) {
    return <p role="status">Sin movimientos pendientes</p>;
  }
  return (
    <ul className="item-list" aria-label="Movimientos pendientes">
      {candidates.map((candidate) => (
        <li className="surface-solid" key={candidate.entry_id}>
          <label className="check-field">
            <input
              type="checkbox"
              checked={selected.has(candidate.entry_id)}
              onChange={(event) =>
                onChange(candidate.entry_id, event.currentTarget.checked)
              }
            />
            <span>
              <span>{candidate.description ?? "Sin descripción"}</span>
              {" · "}
              <span>{candidate.eligibility_date}</span>
              {" · "}
              <span className="money">
                {formatEurCents(candidate.effect_cents)}
              </span>
            </span>
          </label>
          {candidate.kind === "OPENING" ? (
            <strong className="status">Base inicial</strong>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
