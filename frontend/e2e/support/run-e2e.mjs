import { existsSync, readFileSync, rmSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

import { createRuntimeControl } from "./runtime-control.mjs";

const runtimeControl = createRuntimeControl();
const runtimeFile = runtimeControl.file;
const cli = resolve("node_modules/@playwright/test/cli.js");

const result = spawnSync(
  process.execPath,
  [cli, "test", ...process.argv.slice(2)],
  {
    env: {
      ...process.env,
      PF_E2E_RUNTIME_FILE: runtimeFile,
    },
    stdio: "inherit",
    windowsHide: true,
  },
);

let cleanupFailed = false;
try {
  if (existsSync(runtimeFile)) {
    const runtime = JSON.parse(readFileSync(runtimeFile, "utf8"));
    rmSync(runtime.workspace ?? runtime.root, {
      recursive: true,
      force: true,
      maxRetries: 20,
      retryDelay: 100,
    });
  }
} catch (error) {
  cleanupFailed = true;
  console.error(`E2E cleanup failed: ${String(error)}`);
} finally {
  rmSync(runtimeControl.directory, { recursive: true, force: true });
}

process.exitCode = cleanupFailed ? 1 : (result.status ?? 1);
