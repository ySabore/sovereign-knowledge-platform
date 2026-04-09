import { useState, useEffect, type ReactNode } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

interface AdminPermissionGuardProps {
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Wrapper for admin surfaces that may hit admin-only endpoints.
 * On 403 or endpoint missing, shows fallback instead of crashing.
 */
export function AdminPermissionGuard({ children, fallback }: AdminPermissionGuardProps) {
  const { user } = useAuth();
  const [hasAccess, setHasAccess] = useState<boolean | null>(null);

  useEffect(() => {
    // Platform owner always has access
    if (user?.is_platform_owner) {
      setHasAccess(true);
      return;
    }

    // Org owner has access
    if ((user?.org_ids_as_owner?.length ?? 0) > 0) {
      setHasAccess(true);
      return;
    }

    // Test admin access by probing metrics endpoint
    api
      .get("/admin/metrics/summary")
      .then(() => setHasAccess(true))
      .catch((e) => {
        const status = e.response?.status;
        // 403 = no permission, 404 = endpoint not available
        if (status === 403 || status === 404) {
          setHasAccess(false);
        } else {
          // Other errors - assume no access to be safe
          setHasAccess(false);
        }
      });
  }, [user]);

  if (hasAccess === null) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "var(--muted)" }}>
        Checking admin access...
      </div>
    );
  }

  if (!hasAccess) {
    if (fallback) {
      return <>{fallback}</>;
    }
    return (
      <div
        style={{
          padding: "2rem",
          textAlign: "center",
          background: "var(--surface2)",
          borderRadius: "12px",
          border: "1px solid var(--border)",
        }}
      >
        <div style={{ fontSize: "1.25rem", marginBottom: "0.5rem" }}>🔒 Admin Access Required</div>
        <div style={{ color: "var(--muted)" }}>
          This feature is only available to organization owners and platform administrators.
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
