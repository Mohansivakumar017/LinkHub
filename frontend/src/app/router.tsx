import { Navigate, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import type { ReactNode } from "react";
import { AppShell } from "./AppShell";
import { AuthPage } from "../features/auth/pages/AuthPage";
import { SharedLinkPage } from "../features/shared-link/pages/SharedLinkPage";
import { LinksPage } from "../features/links/pages/LinksPage";
import { OrganizationsPage } from "../features/organizations/pages/OrganizationsPage";
import { AnalyticsPage } from "../features/analytics/pages/AnalyticsPage";
import { ProfilePage } from "../features/profile/pages/ProfilePage";
import { SettingsPage } from "../features/settings/pages/SettingsPage";
import { ApiKeysPage } from "../features/api-keys/pages/ApiKeysPage";
import { AdminPage } from "../features/admin/pages/AdminPage";
import { appRoutes } from "./routes";
import { useSession } from "../shared/session/SessionProvider";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { tokens } = useSession();
  const location = useLocation();
  if (tokens) return children;
  const returnTo = `${location.pathname}${location.search}`;
  return <Navigate to={`/auth?returnTo=${encodeURIComponent(returnTo)}`} replace />;
}

function RootEntry() {
  const [params] = useSearchParams();
  return params.get("link") ? <SharedLinkPage /> : <AuthPage />;
}

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<RootEntry />} />
        <Route path="/auth" element={<AuthPage />} />
        <Route path={appRoutes.sharedLink} element={<SharedLinkPage />} />
        <Route path="/workspace/links" element={<ProtectedRoute><LinksPage /></ProtectedRoute>} />
        <Route path="/workspace/links/create" element={<ProtectedRoute><LinksPage /></ProtectedRoute>} />
        <Route path="/workspace/links/import" element={<ProtectedRoute><LinksPage /></ProtectedRoute>} />
        <Route path="/organizations" element={<ProtectedRoute><OrganizationsPage /></ProtectedRoute>} />
        <Route path="/analytics" element={<ProtectedRoute><AnalyticsPage /></ProtectedRoute>} />
        <Route path={appRoutes.profile} element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
        <Route path={appRoutes.settings} element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/api-keys" element={<ProtectedRoute><ApiKeysPage /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/workspace/links" replace />} />
      </Route>
    </Routes>
  );
}
