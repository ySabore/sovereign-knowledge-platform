import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "./AuthContext";

const STORAGE_KEY = "skp_platform_nav_v1";

export type NavigationScope = "platform" | "organization";

type Persisted = {
  scope: NavigationScope;
  activeOrganizationId: string | null;
};

function readPersisted(): Persisted | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as Persisted;
    if (p.scope !== "platform" && p.scope !== "organization") return null;
    return { scope: p.scope, activeOrganizationId: p.activeOrganizationId ?? null };
  } catch {
    return null;
  }
}

function writePersisted(p: Persisted): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch {
    /* ignore */
  }
}

export type PlatformNavigationValue = {
  navigationScope: NavigationScope;
  activeOrganizationId: string | null;
  activeWorkspaceId: string | null;
  activeWorkspaceName: string | null;
  setActiveWorkspaceContext: (id: string | null, name: string | null) => void;
  enterOrganization: (organizationId: string) => void;
  exitToPlatform: () => void;
  needsOrganizationContext: boolean;
  isPlatformOwner: boolean;
};

const PlatformNavigationContext = createContext<PlatformNavigationValue | null>(null);

function guestSetActiveWorkspaceContext(_id: string | null, _name: string | null) {}
function guestEnterOrganization(_organizationId: string) {}
function guestExitToPlatform() {}

/** Safe value when the user is not authenticated; keeps `usePlatformNavigation` from throwing. */
const GUEST_PLATFORM_NAVIGATION: PlatformNavigationValue = {
  navigationScope: "platform",
  activeOrganizationId: null,
  activeWorkspaceId: null,
  activeWorkspaceName: null,
  setActiveWorkspaceContext: guestSetActiveWorkspaceContext,
  enterOrganization: guestEnterOrganization,
  exitToPlatform: guestExitToPlatform,
  needsOrganizationContext: false,
  isPlatformOwner: false,
};

export function PlatformNavigationProvider({
  children,
  orgIds,
}: {
  children: ReactNode;
  /** Stable list of organization ids (e.g. `orgs.map((o) => o.id)` memoized on `orgs`). */
  orgIds: string[];
}) {
  const { user } = useAuth();
  const isPlatformOwner = Boolean(user?.is_platform_owner);

  const [navigationScope, setNavigationScope] = useState<NavigationScope>(() =>
    isPlatformOwner ? "platform" : "organization",
  );
  const [activeOrganizationId, setActiveOrganizationId] = useState<string | null>(null);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [activeWorkspaceName, setActiveWorkspaceName] = useState<string | null>(null);

  const seededRef = useRef(false);

  /** Allow bootstrap again after login/logout or account switch (refs survive guest vs authed render). */
  useEffect(() => {
    seededRef.current = false;
  }, [user?.id]);

  // One-time bootstrap when organization ids become available
  useEffect(() => {
    if (!user || !orgIds.length) return;
    if (seededRef.current) return;
    seededRef.current = true;

    if (isPlatformOwner) {
      const p = readPersisted();
      if (p?.scope === "organization" && p.activeOrganizationId && orgIds.includes(p.activeOrganizationId)) {
        setNavigationScope("organization");
        setActiveOrganizationId(p.activeOrganizationId);
      } else {
        setNavigationScope("platform");
        setActiveOrganizationId(null);
      }
    } else {
      setNavigationScope("organization");
      setActiveOrganizationId(orgIds[0] ?? null);
    }
  }, [user, isPlatformOwner, orgIds]);

  // Drop invalid org if membership list changes
  useEffect(() => {
    if (!user || !orgIds.length || !activeOrganizationId) return;
    if (orgIds.includes(activeOrganizationId)) return;
    if (isPlatformOwner) {
      setNavigationScope("platform");
      setActiveOrganizationId(null);
      writePersisted({ scope: "platform", activeOrganizationId: null });
    } else {
      setActiveOrganizationId(orgIds[0] ?? null);
    }
  }, [user, isPlatformOwner, orgIds, activeOrganizationId]);

  const enterOrganization = useCallback(
    (organizationId: string) => {
      if (!orgIds.includes(organizationId)) return;
      setNavigationScope("organization");
      setActiveOrganizationId(organizationId);
      if (isPlatformOwner) {
        writePersisted({ scope: "organization", activeOrganizationId: organizationId });
      }
    },
    [orgIds, isPlatformOwner],
  );

  const exitToPlatform = useCallback(() => {
    if (!isPlatformOwner) return;
    setNavigationScope("platform");
    setActiveOrganizationId(null);
    setActiveWorkspaceId(null);
    setActiveWorkspaceName(null);
    writePersisted({ scope: "platform", activeOrganizationId: null });
  }, [isPlatformOwner]);

  const setActiveWorkspaceContext = useCallback((id: string | null, name: string | null) => {
    setActiveWorkspaceId(id);
    setActiveWorkspaceName(name);
  }, []);

  const needsOrganizationContext = Boolean(isPlatformOwner && navigationScope === "platform");

  const value = useMemo<PlatformNavigationValue>(
    () => ({
      navigationScope,
      activeOrganizationId,
      activeWorkspaceId,
      activeWorkspaceName,
      setActiveWorkspaceContext,
      enterOrganization,
      exitToPlatform,
      needsOrganizationContext,
      isPlatformOwner,
    }),
    [
      navigationScope,
      activeOrganizationId,
      activeWorkspaceId,
      activeWorkspaceName,
      setActiveWorkspaceContext,
      enterOrganization,
      exitToPlatform,
      needsOrganizationContext,
      isPlatformOwner,
    ],
  );

  if (!user) {
    return (
      <PlatformNavigationContext.Provider value={GUEST_PLATFORM_NAVIGATION}>
        {children}
      </PlatformNavigationContext.Provider>
    );
  }

  return (
    <PlatformNavigationContext.Provider value={value}>{children}</PlatformNavigationContext.Provider>
  );
}

export function usePlatformNavigation(): PlatformNavigationValue {
  const v = useContext(PlatformNavigationContext);
  if (!v) {
    throw new Error("usePlatformNavigation must be used within PlatformNavigationProvider");
  }
  return v;
}

export function usePlatformNavigationOptional(): PlatformNavigationValue | null {
  return useContext(PlatformNavigationContext);
}
