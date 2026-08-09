import { spawn, type ChildProcess } from "node:child_process";
import { createServer } from "node:net";
import { join } from "node:path";

export interface BootstrapState {
  readonly root: string;
  readonly database_url: string;
  readonly ca: string;
  readonly cert: string;
  readonly key: string;
  readonly spki: string;
  readonly username: string;
  readonly password: string;
  readonly secret_key: string;
  readonly server_python?: string;
  readonly installed_site?: string;
}

export async function freeLoopbackPort(): Promise<number> {
  return await new Promise((resolvePort, reject) => {
    const server = createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (address === null || typeof address === "string") {
        reject(new Error("No loopback port assigned"));
        return;
      }
      server.close(() => resolvePort(address.port));
    });
  });
}

export function backendPython(repo: string): string {
  return process.platform === "win32"
    ? join(repo, "backend", ".venv", "Scripts", "python.exe")
    : join(repo, "backend", ".venv", "bin", "python");
}

export function startServer(
  repo: string,
  state: BootstrapState,
  port: number,
): ChildProcess {
  const logs = join(state.root, "server.log");
  const child = spawn(
    state.server_python ?? backendPython(repo),
    [
      "-m",
      "uvicorn",
      "app.main:create_app",
      "--factory",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--ssl-certfile",
      state.cert,
      "--ssl-keyfile",
      state.key,
    ],
    {
      cwd: state.root,
      env: {
        ...process.env,
        PYTHONPATH: state.installed_site,
        PF_DATABASE_URL: state.database_url,
        PF_SECRET_KEY: state.secret_key,
        PF_ALLOWED_ORIGIN: `https://127.0.0.1:${port}`,
        PF_DOMESTIC_TIMEZONE: "Europe/Madrid",
      },
      stdio: ["ignore", "ignore", "ignore"],
      windowsHide: true,
    },
  );
  child.once("error", (error) => {
    throw new Error(`E2E server failed (${logs}): ${error.message}`);
  });
  return child;
}
