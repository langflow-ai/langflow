import { useAuth } from "@clerk/clerk-react";
import { useEffect } from "react";
import { Cookies } from "react-cookie";
import useAuthStore from "@/stores/authStore";
import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";

export default function ClerkAuthAdapter() {
  const { getToken, isSignedIn, sessionId } = useAuth();

  useEffect(() => {
    const cookies = new Cookies();
    async function syncToken() {
      if (isSignedIn) {
        const token = await getToken();
        if (token) {
          cookies.set(LANGFLOW_ACCESS_TOKEN, token, { path: "/" });
          useAuthStore.getState().setAccessToken(token);
          useAuthStore.getState().setIsAuthenticated(true);
        }
      } else {
        cookies.remove(LANGFLOW_ACCESS_TOKEN, { path: "/" });
        useAuthStore.getState().logout();
      }
    }
    syncToken();
  }, [isSignedIn, getToken, sessionId]);

  return null;
}
