import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { createApiClient, type SessionTokens } from "../api/client";
import { readSession, saveSession, clearSession } from "./session";

type SessionContextValue = {
  tokens: SessionTokens | null;
  setTokens: (tokens: SessionTokens) => void;
  clear: () => void;
  api: ReturnType<typeof createApiClient>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [tokens, setTokenState] = useState<SessionTokens | null>(() => readSession());
  const setTokens = (next: SessionTokens) => { saveSession(next); setTokenState(next); };
  const clear = () => { clearSession(); setTokenState(null); };
  const api = useMemo(() => createApiClient(setTokenState), []);
  return <SessionContext.Provider value={{ tokens, setTokens, clear, api }}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside AppShell");
  return value;
}
