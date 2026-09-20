import { Navigate, Route, Routes } from "react-router-dom";
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
import { useSearchParams } from "react-router-dom";

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
        <Route path="/workspace/links" element={<LinksPage />} />
        <Route path="/organizations" element={<OrganizationsPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path={appRoutes.profile} element={<ProfilePage />} />
        <Route path={appRoutes.settings} element={<SettingsPage />} />
        <Route path="/api-keys" element={<ApiKeysPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/workspace/links" replace />} />
      </Route>
    </Routes>
  );
}
