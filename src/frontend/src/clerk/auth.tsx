import { lazy, ReactNode, useContext, useEffect, useRef } from "react";
import { AuthContext } from "@/contexts/authContext";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useLogout as useLogoutMutation } from "@/controllers/API/queries/auth";
import { ClerkProvider, useAuth, useClerk, useUser } from "@clerk/clerk-react";
import { Users } from "@/types/api";
import { LANGFLOW_ACCESS_TOKEN, LANGFLOW_REFRESH_TOKEN } from "@/constants/constants";
import { Cookies } from "react-cookie";

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
  return res.data;
}

// Component that syncs Clerk session with backend
export function ClerkAuthAdapter() {
  const { getToken, isSignedIn, sessionId } = useAuth();
  const { user } = useUser();
  const { login } = useContext(AuthContext);
  const { mutateAsync: logout } = useLogout();
  const prevSession = useRef<string | null>(null);
  const justLoggedIn = useRef(false);
  const clerk = useClerk();
  const cookie = new Cookies();

  useEffect(() => {
    const syncToken = async () => {
      if (!isSignedIn || sessionId === prevSession.current) return;

      prevSession.current = sessionId;

      const token = await getToken();
      if (!token) {
        console.warn("[ClerkAuthAdapter] No Clerk token available");
        return;
      }
      const username =
        user?.username ||
        user?.primaryEmailAddress?.emailAddress ||
        user?.id ||
        "clerk_user";

      try {
        const { justCreated, user } = await ensureLangflowUser(token, username);

        if (justCreated=== true && !user) {
          console.warn("[ClerkAuthAdapter] User created → Signing out to restart session");
          await logout();
          window.location.replace("/login");
          return;
        }

        const { refresh_token } = await backendLogin(username, token);
        login(token, "login", refresh_token);
        justLoggedIn.current = true;
        console.debug("[ClerkAuthAdapter] login complete");
      } catch (err) {
        if (!justLoggedIn.current) {
          console.error("[ClerkAuthAdapter] syncToken error:", err);
          await logout();
        } else {
          console.warn("[ClerkAuthAdapter] Skipping logout due to recent login");
        }
      }
    };

    syncToken();
  }, [isSignedIn, sessionId, getToken, user, login, logout]);

const prevTokenRef = useRef<string | null>(null);
useEffect(() => {
    const unsubscribe = clerk.addListener(async ({ session }) => {
      console.debug("[ClerkAuthAdapter] Token update event received");
      const token = await session?.getToken();
      if (!token) return;
      const current = cookie.get(LANGFLOW_ACCESS_TOKEN);
      if (prevTokenRef.current === null) {
        // Ignore the initial event triggered on sign-in.
        prevTokenRef.current = token;
        return;
      }
      console.debug("[ClerkAuthAdapter] Is Token Same:", token === current);
      if (token !== prevTokenRef.current) {
        prevTokenRef.current = token;
        const current = cookie.get(LANGFLOW_ACCESS_TOKEN);
        if (token !== current) {
          const currentRefreshToken = cookie.get(LANGFLOW_REFRESH_TOKEN);
          login(token,"login",currentRefreshToken)
        }
      }
    });
    return () => {
      unsubscribe?.();
    };
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
    clerkSignOut().finally(() => mutate(...args));
  };

  const wrappedMutateAsync: typeof mutateAsync = async (...args) => {
    await clerkSignOut();
    return mutateAsync(...args);
  };

  return { mutate: wrappedMutate, mutateAsync: wrappedMutateAsync, clerkSignOut, ...rest };
}

// App wrapper that conditionally enables Clerk
const LazyApp = lazy(() => import("../customization/custom-App"));

export function AppWithProvider() {
  return IS_CLERK_AUTH ? (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
      <LazyApp />
    </ClerkProvider>
  ) : (
      <LazyApp />
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

export default AppWithProvider;
