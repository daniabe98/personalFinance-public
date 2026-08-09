import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";

import { runtimeFile } from "./global-setup";

export default async function globalTeardown(): Promise<void> {
  if (!existsSync(runtimeFile)) return;
  const runtime = JSON.parse(readFileSync(runtimeFile, "utf8")) as {
    readonly pid?: number;
  };
  if (runtime.pid !== undefined) {
    try {
      if (process.platform === "win32") {
        execFileSync("taskkill", ["/PID", String(runtime.pid), "/T", "/F"], {
          stdio: "ignore",
          windowsHide: true,
        });
      } else {
        process.kill(runtime.pid, "SIGTERM");
      }
    } catch {
      // Already terminated: teardown remains idempotent.
    }
  }
}
