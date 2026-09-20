import { Outlet } from "react-router-dom";
import { SessionProvider } from "../shared/session/SessionProvider";

/** Stable application boundary for cross-cutting providers and route content. */
export function AppShell() {
  return (
    <SessionProvider>
      <Outlet />
    </SessionProvider>
  );
}
