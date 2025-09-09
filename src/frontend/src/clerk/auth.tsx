import { lazy, ReactNode, useContext, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AuthContext } from "@/contexts/authContext";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useLogout as useLogoutMutation } from "@/controllers/API/queries/auth";
import { ClerkProvider, useAuth, useClerk, useOrganization, useUser, SignedOut } from "@clerk/clerk-react";
import { Users } from "@/types/api";
import { LANGFLOW_ACCESS_TOKEN, LANGFLOW_REFRESH_TOKEN } from "@/constants/constants";
import { Cookies } from "react-cookie";
import OrganizationPage from "./OrganizationPage";
import authStore from "@/stores/authStore";

export const IS_CLERK_AUTH =
  String(import.meta.env.VITE_CLERK_AUTH_ENABLED).toLowerCase() === "true";

export const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";
export const CLERK_DUMMY_PASSWORD = "clerk_dummy_password";

export enum HttpStatusCode {
  UNAUTHORIZED = 401,
  FORBIDDEN = 403,
  NOT_FOUND = 404,
  INTERNAL_SERVER_ERROR = 500
}


export async function createOrganisation(token: string) {
  console.log("[createOrganisation] Called with token:", token);
  try {
    const [, p] = token.split(".");
    console.log("[createOrganisation] Parsed token payload:", JSON.parse(atob(p.replace(/-/g, "+").replace(/_/g, "/"))));
  } catch {
    return null;
  }
  await api.post(
    getURL("CREATE_ORGANISATION"),
    {},
    { headers: { Authorization: `Bearer ${token}` } },
  );
  console.log("[createOrganisation] Organization created via API");
}

// Backend synchronization helpers
export async function ensureLangflowUser(token: string, username: string): Promise<{
  justCreated: boolean;
  user: Users | null;
}> {
  try {
    const whoAmIRes = await api.get<Users>(`${getURL("USERS")}/whoami`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const user = whoAmIRes.data;
    console.debug(`[ensureLangflowUser] user exists: ${username}`);
    return { justCreated: false, user };
  } catch (err: any) {
    const status = err?.response?.status;
    console.warn(`[ensureLangflowUser] whoami failed (${status})`);
    if (status === HttpStatusCode.UNAUTHORIZED) {
      console.debug("[ensureLangflowUser] trying to create user...");
      const createRes = await api.post(
        `${getURL("USERS")}/`,
        { username, password: CLERK_DUMMY_PASSWORD },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      return { justCreated: true, user: null };
    }
    throw err;
  }
}

export async function backendLogin(username: string,token:string) {
  const res = await api.post(
    `${getURL("LOGIN")}`,
    new URLSearchParams({
      username,
      password: CLERK_DUMMY_PASSWORD,
    }).toString(),
    {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization: `Bearer ${token}`,
      },
    },
  );
  console.debug(`[backendLogin] Login response for ${username}:`, res.data);
  return res.data;
}

function useIsOrgSelected(): boolean {
  const storeFlag = authStore((s) => s.isOrgSelected);
  const sessionFlag = sessionStorage.getItem("isOrgSelected") === "true";
  return storeFlag || sessionFlag;
}

export function ClerkAuthAdapter() {
  const { getToken, isSignedIn } = useAuth();
  const clerk = useClerk();
  const { login } = useContext(AuthContext);
  const cookie = new Cookies();
  const navigate = useNavigate();
  const location = useLocation();
  const { organization, isLoaded: isOrgLoaded } = useOrganization();
  const prevTokenRef = useRef<string | null>(null);

  const isOrgSelected = useIsOrgSelected();
  const currentPath = location.pathname;

  const isAtRoot = currentPath === "/";
  const isAtLogin = currentPath === "/login";
  const isAtOrg = currentPath === "/organization";
  console.log("[ClerkAuthAdapter] Render", {
    isSignedIn,
    isOrgSelected,
    currentPath
  });

  // ✅ Redirect to /organization if signed in but org not selected
  useEffect(() => {
    if (
      IS_CLERK_AUTH &&
      isSignedIn &&
      isOrgLoaded &&
      !isOrgSelected &&
      !organization?.id &&
      (isAtRoot || isAtLogin)
    ) {
      console.log("[ClerkAuthAdapter] Redirecting to /organization (no org selected)");
      navigate("/organization", { replace: true });
    }
  }, [isSignedIn, isOrgLoaded, organization?.id, currentPath]);


  // ✅ Clerk token listener: backend sync ONLY after org is selected
  useEffect(() => {
    const unsubscribe = clerk.addListener(async ({ session }) => {
      console.debug("[ClerkAuthAdapter] Token update event received");
      const token = await session?.getToken();
      const orgSelected = sessionStorage.getItem("isOrgSelected") === "true";

      if (!orgSelected) {
        console.debug("[ClerkAuthAdapter] Skipping backend sync (org not selected)");
        prevTokenRef.current = token ?? null;
        return;
      }

      const prevToken = prevTokenRef.current;
      const currentRefreshToken = cookie.get(LANGFLOW_REFRESH_TOKEN);

      if (prevToken === null) {
        prevTokenRef.current = token ?? null;
        return;
      }
      console.debug("[ClerkAuthAdapter] Is Token Same:", token === currentRefreshToken);
      if (token && token !== prevToken) {
        console.log("[ClerkAuthAdapter] Detected token change, syncing with backend");
        prevTokenRef.current = token;
        login(token, "login", currentRefreshToken);
      }
    });

    return () => unsubscribe?.();
  }, [clerk]);

  return null;
}

// Provider that wraps the app with Clerk when enabled
export function ClerkAuthProvider({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
      {children}
    </ClerkProvider>
  );
}

// Logout hook that also signs out from Clerk
export function useLogout(options?: Parameters<typeof useLogoutMutation>[0]) {
  const { mutate, mutateAsync, ...rest } = useLogoutMutation(options);
  const { signOut } = IS_CLERK_AUTH ? useClerk() : { signOut: async () => {} };

  const clerkSignOut = async () => {
    if (IS_CLERK_AUTH) {
      try {
        await signOut();
      } catch (err) {
        console.error("Clerk signOut failed:", err);
      }
    }
  };

  const wrappedMutate: typeof mutate = (...args) => {
    try {
      clerkSignOut();
    } catch (err) {
      console.error("Error occurred during mutation:", err);
    } finally {
      mutate(...args);
    }
  };

  const wrappedMutateAsync: typeof mutateAsync = async (...args) => {
    await clerkSignOut();
    return mutateAsync(...args);
  };

  return { mutate: wrappedMutate, mutateAsync: wrappedMutateAsync, clerkSignOut, ...rest };
}

// App wrapper that conditionally enables Clerk
//const LazyApp = lazy(() => import("../customization/custom-App"));

export default function AppWithProvider({ children }: { children: ReactNode })  {
  return IS_CLERK_AUTH ? (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
      {children}
    </ClerkProvider>
  ) : (
      <>{children}</>
  );
  
}

// Mock mutation used when Clerk auth is enabled
export const mockClerkMutation = {
  mutate: () => {},
  mutateAsync: async () => undefined,
  isError: false,
  isIdle: true,
  isPending: false,
  isSuccess: true,
  reset: () => {},
  status: "success",
  variables: undefined,
  data: undefined,
  error: null,
} as any;
