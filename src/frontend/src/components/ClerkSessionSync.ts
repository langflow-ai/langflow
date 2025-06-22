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
      setUserData({
        username: user.username || user.id,
        email: user.primaryEmailAddress?.emailAddress,
        id: user.id,
      });
    }
  }, [isSignedIn, user]);

  return null;
}
