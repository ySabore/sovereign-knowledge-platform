import { Navigate, Outlet, Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { clerkEnabled } from "./lib/clerkEnv";
import { SkeletonBlock } from "./components/Skeleton";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { ClerkSignInPage } from "./pages/ClerkSignInPage";
import { ClerkSignUpPage } from "./pages/ClerkSignUpPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { DashboardPage } from "./pages/app/DashboardPage";
import { EnterpriseUiReplicaPage } from "./pages/app/EnterpriseUiReplicaPage";
import { AdminConnectorsPage } from "./pages/app/AdminConnectorsPage";
import { AdminDashboardPage } from "./pages/app/AdminDashboardPage";
import { AdminDocumentsPage } from "./pages/app/AdminDocumentsPage";
import { AdminTeamPage } from "./pages/app/AdminTeamPage";
import { AdminBillingPage } from "./pages/app/AdminBillingPage";
import { AdminAuditPage } from "./pages/app/AdminAuditPage";
import { AdminSettingsPage } from "./pages/app/AdminSettingsPage";
import { MarketingLandingPage } from "./pages/MarketingLandingPage";

/** Legacy URL → canonical dashboard chat */
function WorkspaceToDashboardRedirect() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  if (!workspaceId) return <Navigate to="/home" replace />;
  return <Navigate to={`/dashboard/${workspaceId}`} replace />;
}

function PublicEntryRoute() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ padding: "2rem" }}>
        <SkeletonBlock lines={5} />
      </div>
    );
  }
  if (user) return <Navigate to="/home" replace />;
  return <MarketingLandingPage />;
}

function ProtectedLayout() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ padding: "2rem" }}>
        <SkeletonBlock lines={5} />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<PublicEntryRoute />} />
      <Route path="/login" element={<LoginPage />} />
      {clerkEnabled && (
        <>
          <Route path="/sign-in/*" element={<ClerkSignInPage />} />
          <Route path="/sign-up/*" element={<ClerkSignUpPage />} />
        </>
      )}

      <Route element={<ProtectedLayout />}>
        <Route path="/home" element={<HomePage />} />
        <Route path="/dashboard/:workspaceId" element={<DashboardPage />} />
        <Route path="/workspaces/:workspaceId" element={<WorkspaceToDashboardRedirect />} />
        <Route
          path="/onboarding"
          element={
            <PlaceholderPage
              title="Onboarding"
              detail="Post-signup setup (org/workspace defaults) can be implemented here without changing the API shell."
            />
          }
        />
        <Route path="/admin" element={<AdminDashboardPage />} />
        <Route path="/admin/connectors" element={<AdminConnectorsPage />} />
        <Route path="/admin/documents" element={<AdminDocumentsPage />} />
        <Route path="/admin/team" element={<AdminTeamPage />} />
        <Route path="/admin/billing" element={<AdminBillingPage />} />
        <Route path="/admin/audit" element={<AdminAuditPage />} />
        <Route path="/admin/settings" element={<AdminSettingsPage />} />
        <Route
          path="/admin/usage"
          element={
            <PlaceholderPage
              title="Usage"
              detail="Usage analytics are available under Admin Overview and Billing while the dedicated usage page is finalized."
            />
          }
        />
        <Route path="/enterprise-ui" element={<EnterpriseUiReplicaPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
