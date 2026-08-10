import { describe, expect, it, vi } from "vitest";

import { createIdempotencyKey } from "./idempotency-key";

describe("idempotency key", () => {
  it("uses randomUUID when the secure-context API is available", () => {
    const randomUUID = vi.fn(() => "secure-context-uuid");

    expect(
      createIdempotencyKey({
        randomUUID,
        getRandomValues: vi.fn(),
      }),
    ).toBe("secure-context-uuid");
    expect(randomUUID).toHaveBeenCalledOnce();
  });

  it("creates an RFC 4122 version 4 UUID with getRandomValues on HTTP LAN", () => {
    const getRandomValues = vi.fn((target: Uint8Array) => {
      target.set(Array.from({ length: 16 }, (_, index) => index));
      return target;
    });

    expect(createIdempotencyKey({ getRandomValues })).toBe(
      "00010203-0405-4607-8809-0a0b0c0d0e0f",
    );
    expect(getRandomValues).toHaveBeenCalledOnce();
  });
});
