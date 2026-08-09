import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { describe, expect, it, vi } from "vitest";

import "../../test/setup";
import type { ApiClient, ApiRequestOptions, ApiResult } from "../../api/client";
import { createAuthApi, type AuthApi, type SessionResult } from "./api";
import { LoginPage } from "./login-page";
import { SessionProvider, useSession } from "./session-provider";

function AnonymousState(): React.JSX.Element {
  const session = useSession();
  if (session.state === "loading") return <p>Cargando acceso…</p>;
  if (session.state === "authenticated") {
    return (
      <>
        <p>Hola, {session.principal.username}</p>
        <button type="button" onClick={() => void session.logout()}>
          Cerrar sesión
        </button>
      </>
    );
  }
  return <LoginPage />;
}

describe("authentication boundary", () => {
  it("maps the closed session endpoints and public failure reasons", async () => {
    const responses: unknown[] = [
      {
        user_id: "u",
        space_id: "s",
        username: "owner",
        csrf_token: "refreshed",
      },
      {
        csrf_token: "csrf",
        expires_at: "2026-07-31T12:00:00Z",
        user_id: "u",
        space_id: "s",
      },
      null,
    ];
    const calls: string[] = [];
    const client: ApiClient = {
      async request<T>(
        path: `/api/v1/${string}`,
        options?: ApiRequestOptions<T>,
      ): Promise<ApiResult<T>> {
        calls.push(`${options?.method ?? "GET"} ${path}`);
        const value = responses.shift();
        if (options?.validate !== undefined && !options.validate(value)) {
          return {
            ok: false,
            error: {
              kind: "unexpected",
              status: 200,
              code: "invalid_response",
              message: "Respuesta no válida.",
            },
          };
        }
        // The fake validates each queued transport value before exposing it.
        return { ok: true, data: value as T, status: 200 };
      },
    };
    const api = createAuthApi(client);

    expect(await api.session()).toMatchObject({
      ok: true,
      csrfToken: "refreshed",
    });
    expect(await api.login("owner", "secret")).toEqual({
      ok: true,
      principal: { user_id: "u", space_id: "s", username: "owner" },
      csrfToken: "csrf",
    });
    expect(await api.logout()).toEqual({ ok: true });
    expect(calls).toEqual([
      "GET /api/v1/auth/session",
      "POST /api/v1/auth/login",
      "POST /api/v1/auth/logout",
    ]);

    const failureClient: ApiClient = {
      request: vi
        .fn()
        .mockResolvedValueOnce({
          ok: false,
          error: { kind: "unauthorized" },
        })
        .mockResolvedValueOnce({
          ok: false,
          error: { kind: "unauthorized" },
        })
        .mockResolvedValueOnce({
          ok: false,
          error: { kind: "network" },
        }),
    };
    const failingApi = createAuthApi(failureClient);
    expect(await failingApi.session()).toEqual({
      ok: false,
      reason: "unauthorized",
    });
    expect(await failingApi.login("owner", "wrong")).toEqual({
      ok: false,
      reason: "invalid_credentials",
    });
    expect(await failingApi.logout()).toEqual({
      ok: false,
      reason: "unavailable",
    });
  });

  it("keeps protected content hidden until session resolution", async () => {
    let resolveSession: (value: SessionResult) => void = () => undefined;
    const api: AuthApi = {
      session: vi.fn<() => Promise<SessionResult>>(
        () =>
          new Promise<SessionResult>((resolve) => {
            resolveSession = resolve;
          }),
      ),
      login: vi.fn(),
      logout: vi.fn(),
    };
    render(
      <SessionProvider api={api}>
        <AnonymousState />
      </SessionProvider>,
    );

    expect(screen.getByText("Cargando acceso…")).toBeInTheDocument();
    expect(screen.queryByText(/Hola/)).not.toBeInTheDocument();
    resolveSession({ ok: false, reason: "unauthorized" });

    expect(
      await screen.findByRole("heading", { name: "Acceder" }),
    ).toBeVisible();
  });

  it("uses visible labels, validates fields and announces generic failure", async () => {
    const user = userEvent.setup();
    const api: AuthApi = {
      session: vi.fn().mockResolvedValue({ ok: false, reason: "unauthorized" }),
      login: vi.fn().mockResolvedValue({
        ok: false,
        reason: "invalid_credentials",
      }),
      logout: vi.fn(),
    };
    const { container } = render(
      <SessionProvider api={api}>
        <AnonymousState />
      </SessionProvider>,
    );
    await screen.findByRole("heading", { name: "Acceder" });

    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(screen.getByText("Escribe tu usuario.")).toBeVisible();
    expect(screen.getByText("Escribe tu contraseña.")).toBeVisible();

    await user.type(screen.getByLabelText("Usuario"), "owner");
    await user.type(screen.getByLabelText("Contraseña"), "wrong");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(
      await screen.findByText("No se pudo iniciar sesión. Revisa tus datos."),
    ).toHaveAttribute("role", "alert");
    expect((await axe.run(container)).violations).toEqual([]);
  });

  it("keeps CSRF in memory and clears it on logout", async () => {
    const user = userEvent.setup();
    const api: AuthApi = {
      session: vi.fn().mockResolvedValue({ ok: false, reason: "unauthorized" }),
      login: vi.fn().mockResolvedValue({
        ok: true,
        principal: { user_id: "u", space_id: "s", username: "owner" },
        csrfToken: "memory-only",
      }),
      logout: vi.fn().mockResolvedValue({ ok: true }),
    };
    render(
      <SessionProvider api={api}>
        <AnonymousState />
      </SessionProvider>,
    );
    await screen.findByRole("heading", { name: "Acceder" });
    await user.type(screen.getByLabelText("Usuario"), "owner");
    await user.type(screen.getByLabelText("Contraseña"), "secret");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByText("Hola, owner")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Acceder" })).toBeVisible(),
    );
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
