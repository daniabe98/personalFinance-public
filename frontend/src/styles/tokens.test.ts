import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const globalStyles = readFileSync(
  resolve(process.cwd(), "src/styles/global.css"),
  "utf8",
);
const tokens = readFileSync(
  resolve(process.cwd(), "src/styles/tokens.css"),
  "utf8",
);

describe("Blue Signal and Porcelain tokens", () => {
  it("locks the approved light theme without a V1 dark override", () => {
    expect(tokens).toContain("--color-primary: #154889");
    expect(tokens).toContain("--color-background: #f5f1e8");
    expect(tokens).toContain("--color-surface-solid: #fbf9f4");
    expect(tokens).not.toMatch(/prefers-color-scheme:\s*dark/i);
  });

  it("limits blur to direct large planes and provides a solid fallback", () => {
    expect(globalStyles).toContain(
      "backdrop-filter: blur(18px) saturate(120%)",
    );
    expect(globalStyles).toMatch(/@supports not \(backdrop-filter:/);
    expect(globalStyles).not.toMatch(
      /\.glass-(?:plane|strong)\s+\.glass-(?:plane|strong)/,
    );
    expect(globalStyles).toContain(".surface-solid");
  });

  it("provides 48px controls, dual-tone focus and reduced motion", () => {
    expect(globalStyles).toMatch(/min-height:\s*48px/);
    expect(globalStyles).toMatch(/outline:\s*3px solid/);
    expect(globalStyles).toMatch(/outline-offset:\s*2px/);
    expect(globalStyles).toContain("prefers-reduced-motion: reduce");
  });
});
