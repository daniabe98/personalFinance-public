import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

import "../../test/setup";
import { BackupStatus, type BackupStatusData } from "./backup-status";
import { SettingsPage, type SettingsApi } from "./page";

const backupStates = [
  {
    state: "NEVER_RUN",
    last_valid_backup_date: null,
    last_verification_failure_date: null,
    verification_result: "NOT_AVAILABLE",
    title: "Sin ejecutar",
    explanation: "Todavía no se ha ejecutado ninguna copia de seguridad.",
    verification: "No disponible",
  },
  {
    state: "PENDING",
    last_valid_backup_date: "2026-07-20",
    last_verification_failure_date: null,
    verification_result: "PENDING",
    title: "Pendiente de verificación",
    explanation: "La copia más reciente está esperando verificación.",
    verification: "Pendiente",
  },
  {
    state: "VERIFIED",
    last_valid_backup_date: "2026-07-20",
    last_verification_failure_date: null,
    verification_result: "PASSED",
    title: "Copia verificada",
    explanation: "La copia más reciente se verificó correctamente.",
    verification: "Correcta",
  },
  {
    state: "FAILED",
    last_valid_backup_date: "2026-07-20",
    last_verification_failure_date: "2026-07-22",
    verification_result: "FAILED",
    title: "Verificación fallida",
    explanation: "La copia más reciente no superó la verificación.",
    verification: "Fallida",
  },
] as const;

function settingsApi(): SettingsApi {
  return {
    backupStatus: vi.fn().mockResolvedValue({
      ok: true,
      data: {
        state: "FAILED",
        last_valid_backup_date: "2026-07-20",
        last_verification_failure_date: "2026-07-22",
        verification_result: "FAILED",
        domestic_date: "2026-07-23",
        retention_count: 14,
      },
    }),
    auditEvents: vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        data: {
          events: [
            {
              id: "event-1",
              occurred_at: "2026-07-23T08:00:00Z",
              action: "POSTING",
              result: "SUCCESS",
              actor_id: "owner",
              entity_type: "transaction",
              entity_id: "transaction-1",
              correlation_id: "correlation-1",
              metadata: {
                password: "never-render",
                amount_cents: 123_456,
              },
            },
          ],
          next_cursor: "next-page",
        },
      })
      .mockResolvedValueOnce({
        ok: true,
        data: {
          events: [
            {
              id: "event-2",
              occurred_at: "2026-07-23T09:00:00Z",
              action: "RECONCILIATION_COMPLETED",
              result: "SUCCESS",
              actor_id: null,
              entity_type: "reconciliation",
              entity_id: "reconciliation-1",
              correlation_id: "correlation-2",
              metadata: {},
            },
          ],
          next_cursor: null,
        },
      }),
  };
}

describe("SettingsPage", () => {
  it.each(backupStates)(
    "renders $state with a principal status and four explicit milestones",
    (stateCase) => {
      const status: BackupStatusData = {
        ...stateCase,
        domestic_date: "2026-07-23",
        retention_count: 14,
      };
      const { container } = render(<BackupStatus status={status} />);

      const surface = container.querySelector(".backup-surface");
      if (!(surface instanceof HTMLElement)) {
        throw new Error("Missing backup surface");
      }
      expect(surface).toHaveAttribute("data-backup-state", stateCase.state);
      expect(
        within(surface).getByRole("img", {
          name: `Estado de la copia: ${stateCase.title}`,
        }),
      ).toBeVisible();
      expect(
        within(surface).getByRole("heading", {
          name: stateCase.title,
          level: 3,
        }),
      ).toBeVisible();
      expect(surface).toHaveTextContent(stateCase.explanation);

      const milestones = container.querySelector(".backup-milestones");
      expect(milestones).not.toBeNull();
      expect(milestones?.children).toHaveLength(4);
      expect(milestones).toHaveTextContent("Última copia válida");
      expect(milestones).toHaveTextContent("Verificación");
      expect(milestones).toHaveTextContent("Retención");
      expect(milestones).toHaveTextContent("Próxima ejecución");
      expect(milestones).toHaveTextContent(stateCase.verification);
      expect(container).not.toHaveTextContent(/restaur/i);
      expect(container.querySelector("input[type='file']")).toBeNull();
    },
  );

  it("separates valid backup and failure, paginates redacted audit data, and has no restore control", async () => {
    const user = userEvent.setup();
    const api = settingsApi();
    const { container } = render(<SettingsPage api={api} />);

    expect(await screen.findByText("20 de julio de 2026")).toBeVisible();
    expect(screen.getByText(/falló.*22 de julio de 2026/i)).toBeVisible();
    expect(screen.getByText("Fallida")).toBeVisible();
    expect(screen.getByText("14 copias")).toBeVisible();
    expect(screen.getByText(/24 de julio de 2026/)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Abrir guía de recuperación" }),
    ).toHaveAttribute("href", "/docs/runbooks/backup-restore");
    expect(screen.getByText("Se contabilizó un movimiento.")).toBeVisible();
    expect(container).not.toHaveTextContent("never-render");
    expect(container).not.toHaveTextContent("123456");
    expect(
      screen.queryByRole("button", { name: /restaur/i }),
    ).not.toBeInTheDocument();
    expect(container.querySelector("input[type='file']")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Cargar más" }));
    expect(
      await screen.findByText("Se completó una conciliación."),
    ).toBeVisible();
    expect(api.auditEvents).toHaveBeenLastCalledWith("next-page");
    expect((await axe.run(container)).violations).toEqual([]);
  });

  it("announces empty and error states", async () => {
    const emptyApi: SettingsApi = {
      backupStatus: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          state: "NEVER_RUN",
          last_valid_backup_date: null,
          last_verification_failure_date: null,
          verification_result: "NOT_AVAILABLE",
          domestic_date: "2026-07-23",
          retention_count: 0,
        },
      }),
      auditEvents: vi.fn().mockResolvedValue({
        ok: true,
        data: { events: [], next_cursor: null },
      }),
    };
    const { rerender } = render(<SettingsPage api={emptyApi} />);
    expect(
      await screen.findByText("Todavía no hay copia válida"),
    ).toBeVisible();
    expect(screen.getByText("Sin actividad registrada")).toBeVisible();

    const failedApi: SettingsApi = {
      backupStatus: vi.fn().mockResolvedValue({
        ok: false,
        message: "Sin estado",
      }),
      auditEvents: vi.fn().mockResolvedValue({
        ok: false,
        message: "Sin auditoría",
      }),
    };
    rerender(<SettingsPage api={failedApi} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudieron cargar los ajustes",
    );
  });
});
