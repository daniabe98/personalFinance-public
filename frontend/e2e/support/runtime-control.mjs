import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export function createRuntimeControl() {
  const directory = mkdtempSync(
    join(tmpdir(), "personal-finance-e2e-control-"),
  );
  return Object.freeze({
    directory,
    file: join(directory, "runtime.json"),
  });
}
