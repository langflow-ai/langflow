import { CustomNavigate } from "@/customization/components/custom-navigate";
import useAuthStore from "@/stores/authStore";
import { useAuth } from "@clerk/clerk-react";

// ✅ Clerk support
const IS_CLERK_ENABLED = import.meta.env.VITE_CLERK_AUTH_ENABLED === "true";

export const ProtectedLoginRoute = ({ children }) => {
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // ✅ If using Clerk, allow Clerk's SignedIn/SignedOut to handle auth flow
  const { isSignedIn } = useAuth();
  // ✅ Skip all legacy auth logic if Clerk is active
  if (IS_CLERK_ENABLED) {
    if (isSignedIn) {
      return children;
    }
  }

  if (autoLogin === true || isAuthenticated) {
    const urlParams = new URLSearchParams(window.location.search);
    const redirectPath = urlParams.get("redirect");

    if (redirectPath) {
      return <CustomNavigate to={redirectPath} replace />;
    }
    return <CustomNavigate to="/home" replace />;
  }

  return children;
};
