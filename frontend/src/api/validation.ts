export type Validator<T> = (value: unknown) => value is T;

export type ValidationResult<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly message: string };

export function parseApiResponse<T>(
  value: unknown,
  validator: Validator<T>,
): ValidationResult<T> {
  if (!validator(value)) {
    return {
      ok: false,
      message: "El servidor devolvió una respuesta que no se puede usar.",
    };
  }
  return { ok: true, value };
}

export function isRecord(
  value: unknown,
): value is Readonly<Record<string, unknown>> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
