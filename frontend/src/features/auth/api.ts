import type {
  LoginResponse,
  SessionPrincipal,
  SessionResponse,
} from "../../api/schema";
import type { ApiClient } from "../../api/client";
import { isRecord } from "../../api/validation";

export type SessionResult =
  | {
      readonly ok: true;
      readonly principal: SessionPrincipal;
      readonly csrfToken: string;
    }
  | { readonly ok: false; readonly reason: "unauthorized" | "unavailable" };

export type LoginResult =
  | {
      readonly ok: true;
      readonly principal: SessionPrincipal;
      readonly csrfToken: string;
    }
  | {
      readonly ok: false;
      readonly reason:
        "invalid_credentials" | "insecure_connection" | "unavailable";
    };

export type LogoutResult =
  | { readonly ok: true }
  | { readonly ok: false; readonly reason: "unavailable" };

export interface AuthApi {
  session(): Promise<SessionResult>;
  login(username: string, password: string): Promise<LoginResult>;
  logout(): Promise<LogoutResult>;
}

function isSessionResponse(value: unknown): value is SessionResponse {
  return (
    isRecord(value) &&
    typeof value.user_id === "string" &&
    typeof value.space_id === "string" &&
    typeof value.username === "string" &&
    typeof value.csrf_token === "string"
  );
}

function isLoginResponse(value: unknown): value is LoginResponse {
  return (
    isRecord(value) &&
    typeof value.csrf_token === "string" &&
    typeof value.expires_at === "string" &&
    typeof value.user_id === "string" &&
    typeof value.space_id === "string"
  );
}

export function createAuthApi(client: ApiClient): AuthApi {
  return {
    async session(): Promise<SessionResult> {
      const result = await client.request<SessionResponse>(
        "/api/v1/auth/session",
        { validate: isSessionResponse },
      );
      if (result.ok) {
        return {
          ok: true,
          principal: {
            user_id: result.data.user_id,
            space_id: result.data.space_id,
            username: result.data.username,
          },
          csrfToken: result.data.csrf_token,
        };
      }
      return {
        ok: false,
        reason:
          result.error.kind === "unauthorized" ? "unauthorized" : "unavailable",
      };
    },
    async login(username: string, password: string): Promise<LoginResult> {
      const result = await client.request<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: { username, password },
        csrf: "omit",
        validate: isLoginResponse,
      });
      if (!result.ok) {
        return {
          ok: false,
          reason:
            result.error.kind === "unauthorized"
              ? "invalid_credentials"
              : "unavailable",
        };
      }
      return {
        ok: true,
        principal: {
          user_id: result.data.user_id,
          space_id: result.data.space_id,
          username,
        },
        csrfToken: result.data.csrf_token,
      };
    },
    async logout(): Promise<LogoutResult> {
      const result = await client.request<null>("/api/v1/auth/logout", {
        method: "POST",
      });
      return result.ok ? { ok: true } : { ok: false, reason: "unavailable" };
    },
  };
}
