import { useOrganization } from "@clerk/clerk-react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { clerkEnabled } from "../lib/clerkEnv";
import { SkeletonBlock } from "./Skeleton";

function ClerkOrgAdminOnly({ children }: { children: React.ReactNode }) {
  const { membership, isLoaded } = useOrganization();

  if (!isLoaded) {
    return (
      <div style={{ padding: "2rem" }}>
        <SkeletonBlock lines={4} />
      </div>
    );
  }

  const role = membership?.role;
  const ok = role === "org:admin" || role === "admin";
  if (!ok) {
    return <Navigate to="/home" replace />;
  }
  return <>{children}</>;
}

/**
 * Admin UI: always allow platform owner; with Clerk, also allow org admins.
 * Requires user to be in a Clerk Organization with admin role when using Clerk-only admin path.
 */
export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();

  if (user?.is_platform_owner) {
    return <>{children}</>;
  }

  const jwtOrgAdmin = (user?.org_ids_as_owner?.length ?? 0) > 0;
  if (jwtOrgAdmin) {
    return <>{children}</>;
  }

  if (!clerkEnabled) {
    return <Navigate to="/home" replace />;
  }

  return <ClerkOrgAdminOnly>{children}</ClerkOrgAdminOnly>;
}
