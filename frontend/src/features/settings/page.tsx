import { useEffect, useState } from "react";

import { AuditList, type AuditEvent } from "./audit-list";
import { BackupStatus, type BackupStatusData } from "./backup-status";

type Result<T> =
  | { readonly ok: true; readonly data: T }
  | { readonly ok: false; readonly message: string };

interface AuditPage {
  readonly events: readonly AuditEvent[];
  readonly next_cursor: string | null;
}

export interface SettingsApi {
  backupStatus(): Promise<Result<BackupStatusData>>;
  auditEvents(cursor?: string): Promise<Result<AuditPage>>;
}

export function SettingsPage({
  api,
}: {
  readonly api: SettingsApi;
}): React.JSX.Element {
  const [backup, setBackup] = useState<BackupStatusData>();
  const [events, setEvents] = useState<readonly AuditEvent[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    async function load(): Promise<void> {
      const [backupResult, auditResult] = await Promise.all([
        api.backupStatus(),
        api.auditEvents(),
      ]);
      if (!active) return;
      if (!backupResult.ok || !auditResult.ok) {
        setError(true);
        return;
      }
      setError(false);
      setBackup(backupResult.data);
      setEvents(auditResult.data.events);
      setCursor(auditResult.data.next_cursor);
    }
    void load();
    return () => {
      active = false;
    };
  }, [api]);

  async function loadMore(): Promise<void> {
    if (cursor === null) return;
    const result = await api.auditEvents(cursor);
    if (!result.ok) {
      setError(true);
      return;
    }
    setEvents((current) => [...current, ...result.data.events]);
    setCursor(result.data.next_cursor);
  }

  return (
    <>
      <p className="eyebrow">Espacio privado</p>
      <h1>Ajustes</h1>
      {error ? <p role="alert">No se pudieron cargar los ajustes.</p> : null}
      {backup ? <BackupStatus status={backup} /> : null}
      {!error ? (
        <AuditList
          events={events}
          hasMore={cursor !== null}
          onLoadMore={() => void loadMore()}
        />
      ) : null}
    </>
  );
}
