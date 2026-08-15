import { afterEach, describe, expect, it, vi } from "vitest";

import openapi from "../../openapi.json";
import { createApiClient } from "./client";
import { isRecord, parseApiResponse } from "./validation";
import { formatEurCents, parseEurCents } from "../lib/money";

describe("checked API contract", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("contains only the relative versioned finance surface", () => {
    const paths = Object.keys(openapi.paths);
    expect(paths.length).toBeGreaterThan(10);
    expect(
      paths.every(
        (path) => path.startsWith("/api/v1/") || path.startsWith("/health/"),
      ),
    ).toBe(true);
    expect(JSON.stringify(openapi).toLowerCase()).not.toMatch(
      /debit|credit|journal|restore|upload/,
    );
  });

  it("keeps every money field as integer cents", () => {
    const schemas = Object.values(openapi.components.schemas);
    const moneyFields = schemas.flatMap((schema) =>
      "properties" in schema
        ? Object.entries(schema.properties).filter(([name]) =>
            name.endsWith("_cents"),
          )
        : [],
    );
    expect(moneyFields.length).toBeGreaterThan(0);
    expect(
      moneyFields.every(
        ([, field]) =>
          ("type" in field && field.type === "integer") ||
          ("anyOf" in field &&
            field.anyOf.some(
              (variant: unknown) =>
                isRecord(variant) && variant.type === "integer",
            )),
      ),
    ).toBe(true);
  });

  it("requires normalized descriptions for writes and keeps reads nullable", () => {
    const writeSchemas = [
      openapi.components.schemas.DraftRequest,
      openapi.components.schemas.OpeningRequest,
      openapi.components.schemas.CategoryMovementRequest,
      openapi.components.schemas.TransferRequest,
    ];

    for (const schema of writeSchemas) {
      expect(schema.required).toContain("description");
      expect(schema.properties.description).toMatchObject({
        type: "string",
        minLength: 1,
        maxLength: 500,
      });
    }
    expect(
      openapi.components.schemas.ReversalRequest.properties,
    ).not.toHaveProperty("description");
    expect(
      openapi.components.schemas.TransactionResponse.properties.description,
    ).toMatchObject({
      anyOf: expect.arrayContaining([{ type: "string" }, { type: "null" }]),
    });
  });

  it("publishes enriched report contributions and reconciliation candidates", () => {
    const contribution = openapi.components.schemas.ContributionResponse;
    expect(contribution.required).toContain("description");
    expect(contribution.properties.description).toMatchObject({
      anyOf: expect.arrayContaining([{ type: "string" }, { type: "null" }]),
    });

    const candidate = openapi.components.schemas.CandidateResponse;
    expect(candidate.required).toEqual(
      expect.arrayContaining(["description", "kind"]),
    );
    expect(candidate.properties.description).toMatchObject({
      anyOf: expect.arrayContaining([{ type: "string" }, { type: "null" }]),
    });
    expect(candidate.properties.kind).toMatchObject({
      $ref: "#/components/schemas/TransactionKind",
    });
  });

  it("publishes server-projected backup scheduling and a closed failure detail", () => {
    const backup = openapi.components.schemas.BackupStatusResponse;

    expect(backup.required).toEqual(
      expect.arrayContaining([
        "failure_detail",
        "next_expected_execution_date",
      ]),
    );
    expect(backup.properties).not.toHaveProperty("domestic_date");
    expect(backup.properties.failure_detail).toMatchObject({
      anyOf: expect.arrayContaining([
        { $ref: "#/components/schemas/BackupFailureDetail" },
        { type: "null" },
      ]),
    });
  });

  it.each([
    ["0", 0],
    ["12", 1_200],
    ["12,34", 1_234],
    ["1.234,56", 123_456],
    ["-0,01", -1],
  ])("parses %s without binary floating point", (input, expected) => {
    expect(parseEurCents(input)).toEqual({ ok: true, value: expected });
  });

  it("rejects ambiguous or over-precise amounts", () => {
    expect(parseEurCents("1.2")).toMatchObject({ ok: false });
    expect(parseEurCents("1,234")).toMatchObject({ ok: false });
    expect(parseEurCents("12 EUR")).toMatchObject({ ok: false });
  });

  it("formats integer cents through the single EUR boundary", () => {
    expect(formatEurCents(123_456)).toMatch(/1[.\s]234,56\s?€/);
  });

  it("uses relative URLs, cookies, CSRF and caller-stable idempotency", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ transaction_id: "tx-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createApiClient({
      getCsrfToken: () => "csrf-memory-only",
    });

    await client.request("/api/v1/transactions/opening", {
      method: "POST",
      body: { account_id: "a-1", amount_cents: 1_000 },
      idempotencyKey: "stable-key",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/transactions/opening",
      expect.objectContaining({
        credentials: "include",
        headers: expect.objectContaining({
          "X-CSRF-Token": "csrf-memory-only",
          "Idempotency-Key": "stable-key",
        }),
      }),
    );
  });

  it("fails closed when CSRF or the response shape is missing", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const client = createApiClient({
      fetchImplementation: fetchMock,
      getCsrfToken: () => null,
    });

    const missingCsrf = await client.request("/api/v1/accounts", {
      method: "POST",
    });

    expect(missingCsrf).toMatchObject({
      ok: false,
      error: { kind: "forbidden", code: "missing_csrf" },
    });
    expect(fetchMock).not.toHaveBeenCalled();

    const invalidClient = createApiClient({
      fetchImplementation: vi.fn(() =>
        Promise.resolve(Response.json({ unexpected: true })),
      ),
      getCsrfToken: () => "csrf",
    });
    const invalid = await invalidClient.request("/api/v1/accounts", {
      validate: (value): value is { readonly id: string } =>
        isRecord(value) && typeof value.id === "string",
    });
    expect(invalid).toMatchObject({
      ok: false,
      error: { kind: "unexpected", code: "invalid_response" },
    });
  });

  it.each([
    [401, "unauthorized"],
    [403, "forbidden"],
    [409, "conflict"],
    [422, "invalid"],
    [500, "unexpected"],
  ] as const)("maps HTTP %i to the public %s error", async (status, kind) => {
    const onUnauthorized = vi.fn();
    const client = createApiClient({
      fetchImplementation: vi.fn(() =>
        Promise.resolve(
          Response.json(
            { code: "public_code", detail: "Acción no completada." },
            { status },
          ),
        ),
      ),
      getCsrfToken: () => "csrf",
      onUnauthorized,
    });

    const result = await client.request("/api/v1/accounts");

    expect(result).toMatchObject({
      ok: false,
      error: {
        kind,
        code: "public_code",
        message: "Acción no completada.",
      },
    });
    expect(onUnauthorized).toHaveBeenCalledTimes(status === 401 ? 1 : 0);
  });

  it("maps transport failures, empty responses and unstructured errors", async () => {
    const disconnected = createApiClient({
      fetchImplementation: vi.fn(() =>
        Promise.reject(new TypeError("offline")),
      ),
      getCsrfToken: () => "csrf",
    });
    expect(await disconnected.request("/api/v1/accounts")).toMatchObject({
      ok: false,
      error: { kind: "network", status: null },
    });

    const empty = createApiClient({
      fetchImplementation: vi.fn(() =>
        Promise.resolve(new Response(null, { status: 204 })),
      ),
      getCsrfToken: () => "csrf",
    });
    expect(
      await empty.request("/api/v1/auth/logout", { method: "POST" }),
    ).toEqual({
      ok: true,
      data: null,
      status: 204,
    });

    const unstructured = createApiClient({
      fetchImplementation: vi.fn(() =>
        Promise.resolve(Response.json(["private"], { status: 400 })),
      ),
      getCsrfToken: () => "csrf",
    });
    expect(await unstructured.request("/api/v1/accounts")).toMatchObject({
      ok: false,
      error: { kind: "invalid", code: null },
    });
  });

  it("parses trusted values and rejects invalid runtime values", () => {
    const validator = (value: unknown): value is { readonly id: string } =>
      isRecord(value) && typeof value.id === "string";
    expect(parseApiResponse({ id: "ok" }, validator)).toEqual({
      ok: true,
      value: { id: "ok" },
    });
    expect(parseApiResponse([], validator)).toMatchObject({ ok: false });
    expect(isRecord(null)).toBe(false);
    expect(isRecord([])).toBe(false);
  });
});
