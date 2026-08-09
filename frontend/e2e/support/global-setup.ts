import { execFileSync } from "node:child_process";
import { mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { request } from "node:https";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import {
  backendPython,
  freeLoopbackPort,
  startServer,
  type BootstrapState,
} from "./test-server";

const configuredRuntimeFile = process.env.PF_E2E_RUNTIME_FILE;
if (configuredRuntimeFile === undefined) {
  throw new Error("PF_E2E_RUNTIME_FILE must be set by the E2E runner");
}
export const runtimeFile = resolve(configuredRuntimeFile);

async function ready(url: URL, ca: Buffer): Promise<void> {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const ok = await new Promise<boolean>((resolveReady) => {
      const req = request(url, { ca, timeout: 500 }, (response) => {
        response.resume();
        resolveReady(response.statusCode === 200);
      });
      req.on("error", () => resolveReady(false));
      req.on("timeout", () => {
        req.destroy();
        resolveReady(false);
      });
      req.end();
    });
    if (ok) return;
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  throw new Error("HTTPS E2E server did not become ready");
}

export default async function globalSetup(): Promise<void> {
  const repo = resolve(import.meta.dirname, "../../..");
  const root = mkdtempSync(join(tmpdir(), "personal-finance-e2e-"));
  const bootstrap = JSON.parse(
    execFileSync(
      backendPython(repo),
      ["tests/fixtures/e2e_bootstrap.py", "--root", join(root, "state")],
      { cwd: join(repo, "backend"), encoding: "utf8", windowsHide: true },
    ),
  ) as BootstrapState;
  const artifacts = join(root, "artifacts");
  const installedSite = join(root, "installed");
  execFileSync("uv", ["build", "--wheel", "--out-dir", artifacts], {
    cwd: join(repo, "backend"),
    stdio: "ignore",
    windowsHide: true,
  });
  const wheelName = readdirSync(artifacts).find((name) =>
    name.endsWith(".whl"),
  );
  if (wheelName === undefined) {
    throw new Error("E2E wheel build did not produce an artifact");
  }
  execFileSync(
    "uv",
    [
      "pip",
      "install",
      "--offline",
      "--no-deps",
      "--target",
      installedSite,
      join(artifacts, wheelName),
    ],
    { stdio: "ignore", windowsHide: true },
  );
  const state: BootstrapState = {
    ...bootstrap,
    server_python: backendPython(repo),
    installed_site: installedSite,
  };
  const port = await freeLoopbackPort();
  const child = startServer(repo, state, port);
  const runtime = {
    ...state,
    workspace: root,
    port,
    pid: child.pid,
    baseURL: `https://127.0.0.1:${port}`,
  };
  writeFileSync(runtimeFile, JSON.stringify(runtime), { mode: 0o600 });
  try {
    await ready(
      new URL("/health/ready", runtime.baseURL),
      await import("node:fs").then((fs) => fs.readFileSync(state.ca)),
    );
  } catch (error) {
    try {
      if (child.pid !== undefined) process.kill(child.pid, "SIGTERM");
    } catch {
      // The child may already have failed; cleanup below remains authoritative.
    }
    rmSync(root, {
      recursive: true,
      force: true,
      maxRetries: 20,
      retryDelay: 100,
    });
    rmSync(runtimeFile, { force: true });
    throw error;
  }
}
