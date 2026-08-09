import { useState } from "react";

import { ErrorMessage } from "../../ui/feedback";
import { useSession } from "./session-provider";

function connectionIsSafe(): boolean {
  const hostname = window.location.hostname;
  return (
    window.location.protocol === "https:" ||
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1"
  );
}

export function LoginPage(): React.JSX.Element {
  const session = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{
    readonly username?: string;
    readonly password?: string;
    readonly summary?: string;
  }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSafe = connectionIsSafe();

  if (session.state !== "anonymous") {
    return <p role="status">Preparando tu espacio…</p>;
  }
  const login = session.login;

  async function submit(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    const nextErrors = {
      ...(username.trim() === "" ? { username: "Escribe tu usuario." } : {}),
      ...(password === "" ? { password: "Escribe tu contraseña." } : {}),
    };
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }
    setIsSubmitting(true);
    setErrors({});
    const result = await login(username.trim(), password);
    setIsSubmitting(false);
    if (!result.ok) {
      setErrors({
        summary:
          result.reason === "unavailable"
            ? "No se pudo conectar. Inténtalo de nuevo."
            : "No se pudo iniciar sesión. Revisa tus datos.",
      });
    }
  }

  return (
    <main className="login-layout">
      <section
        className="glass-strong login-panel"
        aria-labelledby="login-title"
      >
        <p className="eyebrow">Tu espacio privado</p>
        <h1 id="login-title">Acceder</h1>
        <p>Consulta y organiza tus finanzas desde tu red de confianza.</p>
        {!isSafe ? (
          <ErrorMessage>
            Esta conexión no es segura. Abre la dirección HTTPS indicada por tu
            servidor doméstico.
          </ErrorMessage>
        ) : null}
        {errors.summary !== undefined ? (
          <ErrorMessage>{errors.summary}</ErrorMessage>
        ) : null}
        <form
          className="surface-solid login-form"
          onSubmit={(event) => void submit(event)}
        >
          <div className="field">
            <label htmlFor="username">Usuario</label>
            <input
              autoComplete="username"
              id="username"
              name="username"
              onBlur={() => {
                if (username.trim() === "") {
                  setErrors((current) => ({
                    ...current,
                    username: "Escribe tu usuario.",
                  }));
                }
              }}
              onChange={(event) => setUsername(event.target.value)}
              value={username}
            />
            {errors.username !== undefined ? (
              <span className="field-error" id="username-error">
                {errors.username}
              </span>
            ) : null}
          </div>
          <div className="field">
            <label htmlFor="password">Contraseña</label>
            <input
              autoComplete="current-password"
              id="password"
              name="password"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
            {errors.password !== undefined ? (
              <span className="field-error" id="password-error">
                {errors.password}
              </span>
            ) : null}
          </div>
          <button disabled={isSubmitting || !isSafe} type="submit">
            {isSubmitting ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}
