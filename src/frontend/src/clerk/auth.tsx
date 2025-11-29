import { lazy, ReactNode, useContext, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AuthContext } from "@/contexts/authContext";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useLogout as useLogoutMutation } from "@/controllers/API/queries/auth";
import { ClerkProvider, useAuth, useClerk, useOrganization, useUser } from "@clerk/clerk-react";
import { Users } from "@/types/api";
import { LANGFLOW_ACCESS_TOKEN, LANGFLOW_REFRESH_TOKEN } from "@/constants/constants";
import { Cookies } from "react-cookie";
import OrganizationPage from "./OrganizationPage";
import authStore from "@/stores/authStore";
import {
  getStoredActiveOrgId as readStoredActiveOrgId,
  setStoredActiveOrgId as persistActiveOrgId,
} from "./activeOrgStorage";

export const IS_CLERK_AUTH =
  String(import.meta.env.VITE_CLERK_AUTH_ENABLED).toLowerCase() === "true";

export const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";
export const CLERK_DUMMY_PASSWORD = "clerk_dummy_password";
export {
  ACTIVE_ORG_STORAGE_KEY,
  getStoredActiveOrgId,
  setStoredActiveOrgId,
} from "./activeOrgStorage";

export function getClerkHealthResponse(
  setHealthCheckTimeout: (timeout: string | null) => void,
) {
  setHealthCheckTimeout(null);
  return {
    status: "ok",
    chat: "ok",
    db: "ok",
    folder: "ok",
    variables: "ok",
  } as const;
}

export enum HttpStatusCode {
  UNAUTHORIZED = 401,
  FORBIDDEN = 403,
  NOT_FOUND = 404,
  INTERNAL_SERVER_ERROR = 500
}


export async function createOrganisation(token: string) {
  await api.post(
    getURL("CREATE_ORGANISATION"),
    {},
    { headers: { Authorization: `Bearer ${token}` } },
  );
  console.log("[createOrganisation] Organization created via API");
}

// Backend synchronization helpers
export async function ensureLangflowUser(
  token: string,
  username: string,
  email?: string,
  maxRetries: number = 2
): Promise<{
  justCreated: boolean;
  user: Users | null;
}> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      // Try to fetch existing user
      const whoAmIRes = await api.get<Users>(`${getURL("USERS")}/whoami`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const user = whoAmIRes.data;
      console.debug(`[ensureLangflowUser] user exists: ${username}`);
      return { justCreated: false, user };
      
    } catch (err: any) {
      const status = err?.response?.status;
      console.warn(`[ensureLangflowUser] whoami failed (${status}), attempt ${attempt + 1}/${maxRetries + 1}`);
      
      if (status === HttpStatusCode.UNAUTHORIZED) {
        try {
          // User doesn't exist → create it
          console.debug("[ensureLangflowUser] trying to create user...");
          const optins = IS_CLERK_AUTH
            ? {
                email: email ?? username,
                github_starred: false,
                dialog_dismissed: false,
                discord_clicked: false,
              }
            : undefined;

          await api.post(
            `${getURL("USERS")}/`,
            {
              username,
              password: CLERK_DUMMY_PASSWORD,
              ...(optins ? { optins } : {}),
            },
            { headers: { Authorization: `Bearer ${token}` } },
          );
          console.log(`✅ [ensureLangflowUser] User created successfully: ${username}`);
          return { justCreated: true, user: null };
          
        } catch (createErr: any) {
          // Handle race condition: User created by another tab
          if (createErr?.response?.status === 400 && 
              createErr?.response?.data?.detail?.includes("username is unavailable")) {
            console.debug("[ensureLangflowUser] User created by another tab, retrying whoami...");
            
            // Retry whoami to get the user
            if (attempt < maxRetries) {
              await new Promise(resolve => setTimeout(resolve, 100)); // Small delay
              continue; // Retry from top
            } else {
              console.warn("[ensureLangflowUser] Max retries exceeded after race condition");
            }
          }
          throw createErr; // Re-throw other errors
        }
      }
      
      throw err; // Re-throw non-401 errors
    }
  }
  
  throw new Error("[ensureLangflowUser] Max retries exceeded");
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
  console.debug(`[backendLogin] Login response for ${username}`);
  return res.data;
}

function useIsOrgSelected(): boolean {
  const storeFlag = authStore((s) => s.isOrgSelected);
  const sessionFlag = sessionStorage.getItem("isOrgSelected") === "true";
  return storeFlag || sessionFlag;
}

export function ClerkAuthAdapter() {
  const { getToken, isSignedIn } = useAuth();
  const { user } = useUser();
  const clerk = useClerk();
  const { login } = useContext(AuthContext);
  const cookie = new Cookies();
  const navigate = useNavigate();
  const location = useLocation();
  const { organization, isLoaded: isOrgLoaded } = useOrganization();
  const prevTokenRef = useRef<string | null>(null);
  const autoJoinAttemptedRef = useRef(false);

  const isOrgSelected = useIsOrgSelected();
  const currentPath = location.pathname;

  const isAtRoot = currentPath === "/";
  const isAtLogin = currentPath === "/login";
  const activeOrgId = readStoredActiveOrgId();

  console.log("[ClerkAuthAdapter] Render", {
    isSignedIn,
    isOrgSelected,
    currentPath,
    activeOrgId,
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
  }, [isSignedIn, isOrgLoaded, organization?.id, currentPath, navigate, isOrgSelected]);

  // Auto-join the active Clerk organization in fresh tabs with auto-recovery
  useEffect(() => {
    if (!IS_CLERK_AUTH) {
      return;
    }

    if (autoJoinAttemptedRef.current) {
      return;
    }

    if (!isSignedIn || !isOrgLoaded || isOrgSelected || !organization?.id) {
      return;
    }

    const activeOrgId = readStoredActiveOrgId();

    if (!activeOrgId || activeOrgId !== organization.id) {
      return;
    }

    const targetOrgId = organization.id;
    autoJoinAttemptedRef.current = true;

    (async () => {
      try {
        const token = await getToken();

        if (!token) {
          console.warn("[ClerkAuthAdapter] Unable to fetch Clerk token for auto-join");
          autoJoinAttemptedRef.current = false;
          return;
        }

        const refreshToken = cookie.get(LANGFLOW_REFRESH_TOKEN);

        try {
          // Try normal login flow
          login(token, "login", refreshToken);
          sessionStorage.setItem("isOrgSelected", "true");
          authStore.getState().setIsOrgSelected(true);
          persistActiveOrgId(targetOrgId);
          console.debug("[ClerkAuthAdapter] Auto-joined organization", organization?.id);
          
        } catch (loginError: any) {
          // Check if backend session is lost (Docker restart scenario)
          if (loginError?.response?.status === 401 || loginError?.response?.status === 403) {
            console.warn("🔄 [ClerkAuthAdapter] Backend session lost, attempting auto-recovery...");
            
            try {
              // Step 1: Ensure user exists (with retry for race conditions)
              const username = user?.primaryEmailAddress?.emailAddress || user?.id || "clerk_user";
              console.log(`[AutoRecovery] Step 1: Ensuring user exists - ${username}`);
              
              const { justCreated: userCreated } = await ensureLangflowUser(
                token,
                username,
                user?.primaryEmailAddress?.emailAddress,
                2,
              );
              
              if (userCreated) {
                console.log("✅ [AutoRecovery] User created successfully");
              } else {
                console.log("✅ [AutoRecovery] User already exists");
              }
              
              // Step 2: Login to backend (creates new session)
              console.log("[AutoRecovery] Step 2: Creating backend session...");
              const loginRes = await backendLogin(username, token);
              const newRefreshToken = loginRes.refresh_token;
              console.log("✅ [AutoRecovery] Backend session created");
              
              // Step 3: Ensure organization exists
              console.log("[AutoRecovery] Step 3: Ensuring organization exists...");
              try {
                await createOrganisation(token);
                console.log("✅ [AutoRecovery] Organization created/verified");
              } catch (orgErr: any) {
                // Organization might already exist - check if it's a recoverable error
                if (orgErr?.response?.status === 400 || orgErr?.response?.status === 200) {
                  console.log("✅ [AutoRecovery] Organization already exists");
                } else {
                  console.warn("⚠️ [AutoRecovery] Organization creation failed (non-critical):", orgErr?.message);
                  // Continue anyway - org might exist
                }
              }
              
              // Step 4: Update local auth state
              console.log("[AutoRecovery] Step 4: Updating local auth state...");
              login(token, "login", newRefreshToken);
              sessionStorage.setItem("isOrgSelected", "true");
              authStore.getState().setIsOrgSelected(true);
              persistActiveOrgId(targetOrgId);
              
              console.log("✅ [AutoRecovery] Session recovered successfully!");
              
            } catch (recoveryError) {
              console.error("❌ [AutoRecovery] Failed to recover session:", recoveryError);
              autoJoinAttemptedRef.current = false;
              throw recoveryError;
            }
          } else {
            // Other login errors - re-throw
            throw loginError;
          }
        }
      } catch (error) {
        console.error("[ClerkAuthAdapter] Auto-join/recovery failed", error);
        autoJoinAttemptedRef.current = false;
      }
    })();
  }, [isSignedIn, isOrgLoaded, isOrgSelected, organization?.id, user, getToken]);

  // Redirect away from entry routes once the organization is hydrated
  // NOTE: "/" (root) is excluded - authenticated users can stay on landing page
  useEffect(() => {
    if (!IS_CLERK_AUTH) {
      return;
    }

    if (!isSignedIn || !isOrgLoaded || !isOrgSelected) {
      return;
    }

    const activeOrgId = readStoredActiveOrgId();

    if (!activeOrgId || activeOrgId !== organization?.id) {
      return;
    }

    const shouldRedirect =
      currentPath === "/login" || currentPath === "/organization";

    if (!shouldRedirect) {
      return;
    }

    console.debug(
      "[ClerkAuthAdapter] Redirecting initialized tab to /flows",
      currentPath,
    );
    navigate("/flows", { replace: true });
  }, [
    currentPath,
    isSignedIn,
    isOrgLoaded,
    isOrgSelected,
    organization?.id,
    navigate,
  ]);


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
