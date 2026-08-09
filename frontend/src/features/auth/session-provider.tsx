import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { SessionPrincipal } from "../../api/schema";
import type { AuthApi, LoginResult, LogoutResult } from "./api";

type SessionState =
  | { readonly state: "loading" }
  | {
      readonly state: "anonymous";
      readonly login: (
        username: string,
        password: string,
      ) => Promise<LoginResult>;
    }
  | {
      readonly state: "authenticated";
      readonly principal: SessionPrincipal;
      readonly logout: () => Promise<LogoutResult>;
    };

interface SessionContextValue {
  readonly session: SessionState;
  readonly csrfToken: string | null;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({
  api,
  children,
}: {
  readonly api: AuthApi;
  readonly children: React.ReactNode;
}): React.JSX.Element {
  const [principal, setPrincipal] = useState<SessionPrincipal | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [isResolving, setIsResolving] = useState(true);

  useEffect(() => {
    let isActive = true;
    void api.session().then((result) => {
      if (!isActive) return;
      setPrincipal(result.ok ? result.principal : null);
      setCsrfToken(result.ok ? result.csrfToken : null);
      setIsResolving(false);
    });
    return () => {
      isActive = false;
    };
  }, [api]);

  const login = useCallback(
    async (username: string, password: string): Promise<LoginResult> => {
      const result = await api.login(username, password);
      if (result.ok) {
        setPrincipal(result.principal);
        setCsrfToken(result.csrfToken);
      }
      return result;
    },
    [api],
  );

  const logout = useCallback(async (): Promise<LogoutResult> => {
    const result = await api.logout();
    setPrincipal(null);
    setCsrfToken(null);
    return result;
  }, [api]);

  const session = useMemo<SessionState>(() => {
    if (isResolving) return { state: "loading" };
    if (principal === null) return { state: "anonymous", login };
    return { state: "authenticated", principal, logout };
  }, [isResolving, login, logout, principal]);

  const value = useMemo(() => ({ session, csrfToken }), [csrfToken, session]);
  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  const context = useContext(SessionContext);
  if (context === null) {
    throw new Error("useSession must be used inside SessionProvider");
  }
  return context.session;
}

export function useCsrfToken(): string | null {
  const context = useContext(SessionContext);
  if (context === null) {
    throw new Error("useCsrfToken must be used inside SessionProvider");
  }
  return context.csrfToken;
}
