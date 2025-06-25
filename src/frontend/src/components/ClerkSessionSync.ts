// ClerkSessionSync.tsx

import { useEffect } from "react";
import { useUser, useAuth } from "@clerk/clerk-react";
import useAuthStore from "@/stores/authStore";

export function ClerkSessionSync() {
  const { isSignedIn } = useAuth();
  const { user } = useUser();
  const setIsAuthenticated = useAuthStore((s) => s.setIsAuthenticated);
  const setUserData = useAuthStore((s) => s.setUserData);

  useEffect(() => {
    setIsAuthenticated(!!isSignedIn);

    if (isSignedIn && user) {
      setUserData((prev: any) => ({
        ...prev,
        username: user.username,
        email: user.primaryEmailAddress?.emailAddress,
      }));

    }
  }, [isSignedIn, user]);

  return null;
}
