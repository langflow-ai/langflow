import React, { ReactNode, useEffect, useContext, useState } from "react";
import App from "../customization/custom-App";
import { ClerkProvider, useAuth, useUser, useClerk } from "@clerk/clerk-react";
import { Cookies } from "react-cookie";
import useAuthStore from "@/stores/authStore";
import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import { AuthContext } from "@/contexts/authContext";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useLogout as useLogoutMutation } from "@/controllers/API/queries/auth";

// Clerk constants
export const IS_CLERK_AUTH =
  String(process.env.CLERK_AUTH_ENABLED).toLowerCase() === "true";
export const CLERK_PUBLISHABLE_KEY = process.env.CLERK_PUBLISHABLE_KEY || "";
export const CLERK_DUMMY_PASSWORD = "clerk_dummy_password";

// Backend synchronization helpers
export async function ensureLangflowUser(token: string, username: string) {
  try {
    await api.get(`${getURL("USERS")}/whoami`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (err: any) {
    if (err?.response?.status === 404) {
      await api.post(
        `${getURL("USERS")}/`,
        { username, password: CLERK_DUMMY_PASSWORD },
        { headers: { Authorization: `Bearer ${token}` } },
      );
    } else {
      throw err;
    }
  }
}

export async function backendLogin(username: string) {
  const res = await api.post(
    `${getURL("LOGIN")}`,
    new URLSearchParams({
      username,
      password: CLERK_DUMMY_PASSWORD,
    }).toString(),
    {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
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

  useEffect(() => {
    const cookies = new Cookies();
    async function syncToken() {
      if (isSignedIn) {
        const token = await getToken();
        if (token) {
          const username =
            user?.username ||
            user?.primaryEmailAddress?.emailAddress ||
            user?.id ||
            "clerk_user";
          try {
            await ensureLangflowUser(token, username);
            const data = await backendLogin(username);
            login(token, "login", data.refresh_token);
          } catch {
            // ignore errors and continue login
          }
        }
      } else {
        cookies.remove(LANGFLOW_ACCESS_TOKEN, { path: "/" });
        useAuthStore.getState().logout();
      }
    }
    syncToken();
  }, [isSignedIn, getToken, sessionId, user, login]);

  return null;
}

// Provider that wraps the app with Clerk when enabled
export function ClerkAuthProvider({ children }: { children: ReactNode }) {
  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY}>
      <ClerkAuthAdapter />
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
export function AppWithProvider() {
  return IS_CLERK_AUTH ? (
    <ClerkAuthProvider>
      <App />
    </ClerkAuthProvider>
  ) : (
    <App />
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
