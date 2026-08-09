import { isRecord, parseApiResponse, type Validator } from "./validation";

export type ApiErrorKind =
  | "unauthorized"
  | "forbidden"
  | "conflict"
  | "invalid"
  | "network"
  | "unexpected";

export interface ApiError {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string | null;
  readonly message: string;
}

export type ApiResult<T> =
  | { readonly ok: true; readonly data: T; readonly status: number }
  | { readonly ok: false; readonly error: ApiError };

export interface ApiRequestOptions<T> {
  readonly method?: "GET" | "POST" | "PATCH" | "DELETE";
  readonly body?: Readonly<Record<string, unknown>>;
  readonly idempotencyKey?: string;
  readonly csrf?: "required" | "omit";
  readonly validate?: Validator<T>;
}

export interface ApiClient {
  request<T>(
    path: `/api/v1/${string}`,
    options?: ApiRequestOptions<T>,
  ): Promise<ApiResult<T>>;
}

export interface ApiClientOptions {
  readonly getCsrfToken: () => string | null;
  readonly onUnauthorized?: () => void;
  readonly fetchImplementation?: typeof fetch;
}

const UNSAFE_METHODS = new Set(["POST", "PATCH", "DELETE"]);

function errorKind(status: number): ApiErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 409) return "conflict";
  if (status === 400 || status === 422) return "invalid";
  return "unexpected";
}

function errorMessage(payload: unknown): {
  readonly code: string | null;
  readonly message: string;
} {
  if (!isRecord(payload)) {
    return { code: null, message: "No se pudo completar la petición." };
  }
  const detail = typeof payload.detail === "string" ? payload.detail : null;
  const code = typeof payload.code === "string" ? payload.code : null;
  return {
    code,
    message: detail ?? "No se pudo completar la petición.",
  };
}

export function createApiClient(options: ApiClientOptions): ApiClient {
  const fetcher = options.fetchImplementation ?? globalThis.fetch;
  return {
    async request<T>(
      path: `/api/v1/${string}`,
      requestOptions: ApiRequestOptions<T> = {},
    ): Promise<ApiResult<T>> {
      if (!path.startsWith("/api/v1/")) {
        throw new Error("API requests must use the relative versioned surface");
      }
      const method = requestOptions.method ?? "GET";
      const headers: Record<string, string> = {
        Accept: "application/json",
      };
      if (requestOptions.body !== undefined) {
        headers["Content-Type"] = "application/json";
      }
      if (UNSAFE_METHODS.has(method) && requestOptions.csrf !== "omit") {
        const csrfToken = options.getCsrfToken();
        if (csrfToken === null) {
          return {
            ok: false,
            error: {
              kind: "forbidden",
              status: 403,
              code: "missing_csrf",
              message: "Recarga la página e inténtalo de nuevo.",
            },
          };
        }
        headers["X-CSRF-Token"] = csrfToken;
      }
      if (requestOptions.idempotencyKey !== undefined) {
        headers["Idempotency-Key"] = requestOptions.idempotencyKey;
      }

      let response: Response;
      try {
        response = await fetcher(path, {
          method,
          credentials: "include",
          headers,
          ...(requestOptions.body === undefined
            ? {}
            : { body: JSON.stringify(requestOptions.body) }),
        });
      } catch {
        return {
          ok: false,
          error: {
            kind: "network",
            status: null,
            code: null,
            message: "No se pudo conectar con el servidor.",
          },
        };
      }

      const payload: unknown =
        response.status === 204 ? null : await response.json();
      if (!response.ok) {
        if (response.status === 401) {
          options.onUnauthorized?.();
        }
        const publicError = errorMessage(payload);
        return {
          ok: false,
          error: {
            kind: errorKind(response.status),
            status: response.status,
            code: publicError.code,
            message: publicError.message,
          },
        };
      }
      if (requestOptions.validate !== undefined) {
        const parsed = parseApiResponse(payload, requestOptions.validate);
        if (!parsed.ok) {
          return {
            ok: false,
            error: {
              kind: "unexpected",
              status: response.status,
              code: "invalid_response",
              message: parsed.message,
            },
          };
        }
        return { ok: true, data: parsed.value, status: response.status };
      }
      return { ok: true, data: payload as T, status: response.status };
    },
  };
}
