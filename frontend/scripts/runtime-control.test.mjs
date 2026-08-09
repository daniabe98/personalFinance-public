import { existsSync, rmSync } from "node:fs";

import { afterEach, describe, expect, it } from "vitest";

import { createRuntimeControl } from "../e2e/support/runtime-control.mjs";

const directories = [];

afterEach(() => {
  for (const directory of directories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("E2E runtime control", () => {
  it("allocates isolated metadata paths for concurrent runs", () => {
    const first = createRuntimeControl();
    const second = createRuntimeControl();
    directories.push(first.directory, second.directory);

    expect(first.directory).not.toBe(second.directory);
    expect(first.file).not.toBe(second.file);
    expect(existsSync(first.directory)).toBe(true);
    expect(existsSync(second.directory)).toBe(true);
  });
});
