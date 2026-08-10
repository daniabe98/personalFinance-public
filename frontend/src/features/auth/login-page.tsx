import { useState } from "react";

import { ErrorMessage } from "../../ui/feedback";
import { useSession } from "./session-provider";

type ConnectionLocation = Readonly<{
  protocol: string;
  hostname: string;
}>;

function isPrivateIpv4(hostname: string): boolean {
  const octets = hostname.split(".").map(Number);
  if (
    octets.length !== 4 ||
    octets.some((octet) => !Number.isInteger(octet) || octet < 0 || octet > 255)
  ) {
    return false;
  }
  const [first, second] = octets;
  return (
    first === 10 ||
    (first === 172 && second !== undefined && second >= 16 && second <= 31) ||
    (first === 192 && second === 168)
  );
}

export function connectionIsAllowed(
  location: ConnectionLocation = window.location,
): boolean {
  const { hostname, protocol } = location;
  return (
    protocol === "https:" ||
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1" ||
    hostname === "[::1]" ||
    (protocol === "http:" && isPrivateIpv4(hostname))
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
  const isAllowed = connectionIsAllowed();
  const isHttpLan =
    window.location.protocol === "http:" &&
    isPrivateIpv4(window.location.hostname);

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
        {!isAllowed ? (
          <ErrorMessage>
            Esta dirección no está permitida. Usa HTTPS o la IPv4 privada
            indicada por tu servidor doméstico.
          </ErrorMessage>
        ) : null}
        {isHttpLan ? (
          <p className="surface-solid feedback" role="status">
            Conexión HTTP limitada a tu red local de confianza.
          </p>
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
          <button disabled={isSubmitting || !isAllowed} type="submit">
            {isSubmitting ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </section>
    </main>
  );
}
