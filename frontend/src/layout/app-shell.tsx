import { Outlet } from "react-router-dom";

import { LoginPage } from "../features/auth/login-page";
import { useSession } from "../features/auth/session-provider";
import { LoadingState } from "../ui/feedback";
import { PrimaryNav } from "./primary-nav";

export function AppShell(): React.JSX.Element {
  const session = useSession();
  if (session.state === "loading") {
    return (
      <main className="session-loading">
        <LoadingState label="Preparando tu espacio privado…" />
      </main>
    );
  }
  if (session.state === "anonymous") return <LoginPage />;
  return (
    <div className="app-frame">
      <PrimaryNav />
      <main className="glass-plane workspace" id="main-content">
        <header className="session-bar">
          <span>{session.principal.username}</span>
          <button
            className="secondary"
            type="button"
            onClick={() => void session.logout()}
          >
            Cerrar sesión
          </button>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
