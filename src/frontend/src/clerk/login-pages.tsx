import { SignIn, SignUp as ClerkSignUp, useAuth, useUser , useClerk, SignedOut} from "@clerk/clerk-react";
import { lazy, useEffect, useState } from "react";
import { useLogout } from "./auth";
import { IS_CLERK_AUTH } from "@/clerk/auth";
import useAuthStore from "@/stores/authStore";

// Clerk login page component
export function ClerkLoginPage() {
  const { isSignedIn } = useAuth();
  const { signOut } = useClerk();
  const navigate = useCustomNavigate();
  const [processed, setProcessed] = useState(false);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  useEffect(() => {
    // Handle stale Clerk session when local auth is cleared
    if (isSignedIn && !isAuthenticated) {
      console.warn("[ClerkLoginPage] Detected stale Clerk session - cleaning up...");
      signOut()
        .then(() => {
          console.log("[ClerkLoginPage] Stale session cleared successfully");
        })
        .catch((err) => {
          console.error("[ClerkLoginPage] Failed to clear stale session:", err);
          // Force reload to clear everything
          window.location.reload();
        });
      return;
    }

    if (isSignedIn && isAuthenticated && !processed) {
      setProcessed(true);
      navigate("/organization");
    }
  }, [isSignedIn, isAuthenticated, navigate, processed, signOut]);

  return (
    <SignedOut>
      <div style={centeredStyle}>
        <SignIn
          afterSignInUrl="/organization"
          redirectUrl="/organization"
        />
      </div>
    </SignedOut>
  );
}

// Clerk sign-up page component
export function ClerkSignUpPage() {
  const { isSignedIn } = useAuth();
  const { user } = useUser();
  const navigate = useCustomNavigate();
  const [processed, setProcessed] = useState(false);

  useEffect(() => {
    async function handleSignup() {
      if (isSignedIn && user && !processed) {
        setProcessed(true);
        navigate("/organization");
      }
    }
    handleSignup();
  }, [isSignedIn, user, navigate, processed]);

  return (
    <SignedOut>
      <div style={centeredStyle}>
        <ClerkSignUp
          path="/sign-up"
          routing="path"
          afterSignUpUrl="/organization"
          redirectUrl="/organization"
        />
      </div>
    </SignedOut>
  );
}

// Original pages
import OriginalLoginPage from "../pages/LoginPage";
import OriginalSignUp from "../pages/SignUpPage";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
const OriginalLoginAdminPage = lazy(() => import("../pages/AdminPage/LoginPage"));

export const LoginPage = IS_CLERK_AUTH ? ClerkLoginPage : OriginalLoginPage;
export const SignUp = IS_CLERK_AUTH ? ClerkSignUpPage : OriginalSignUp;
export const LoginAdminPage = IS_CLERK_AUTH ? ClerkLoginPage : OriginalLoginAdminPage;

const centeredStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  minHeight: "100vh",
};

