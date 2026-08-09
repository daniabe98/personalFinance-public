import "@testing-library/jest-dom/vitest";

import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// React Router receives jsdom AbortSignals while Node's Request accepts only
// its own realm. Navigation tests do not need to forward that cancellation.
const NativeRequest = globalThis.Request;
class CompatibleRequest extends NativeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal !== undefined) {
      const { signal: _signal, ...compatibleInit } = init;
      super(input, compatibleInit);
      return;
    }
    super(input, init);
  }
}
globalThis.Request = CompatibleRequest;
vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
  measureText: () => ({ width: 0 }),
} as unknown as CanvasRenderingContext2D);
const nativeGetComputedStyle = window.getComputedStyle.bind(window);
vi.spyOn(window, "getComputedStyle").mockImplementation((element) =>
  nativeGetComputedStyle(element),
);

afterEach(() => {
  cleanup();
});
