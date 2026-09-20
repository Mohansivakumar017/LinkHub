import { sessionStorageKeys, type SessionTokens } from "../api/client";

export function readSession(): SessionTokens | null {
  const accessToken = localStorage.getItem(sessionStorageKeys.access);
  const refreshToken = localStorage.getItem(sessionStorageKeys.refresh);
  return accessToken ? { accessToken, refreshToken: refreshToken ?? "" } : null;
}

export function saveSession(tokens: SessionTokens) {
  localStorage.setItem(sessionStorageKeys.access, tokens.accessToken);
  localStorage.setItem(sessionStorageKeys.refresh, tokens.refreshToken);
}

export function clearSession() {
  localStorage.removeItem(sessionStorageKeys.access);
  localStorage.removeItem(sessionStorageKeys.refresh);
}
