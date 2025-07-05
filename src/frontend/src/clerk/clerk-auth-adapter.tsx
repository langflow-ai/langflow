import { useAuth, useUser } from "@clerk/clerk-react";
import { useEffect, useContext } from "react";
import { Cookies } from "react-cookie";
import useAuthStore from "@/stores/authStore";
import { LANGFLOW_ACCESS_TOKEN } from "@/constants/constants";
import { AuthContext } from "@/contexts/authContext";
import { ensureLangflowUser, backendLogin } from "./langflow-sync";

export default function ClerkAuthAdapter() {
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
            // use the Clerk token for frontend state but still
            // rely on /login to set refresh and API key cookies
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
