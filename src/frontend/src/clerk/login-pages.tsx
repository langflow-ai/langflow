import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { SignIn, SignUp, useAuth, useUser , useClerk, SignedOut} from "@clerk/clerk-react";
import { lazy, useEffect, useState } from "react";
import { ensureLangflowUser, useLogout } from "./auth";
import { IS_CLERK_AUTH } from "@/clerk/constants";
// Clerk login page component
export function ClerkLoginPage() {
  return (
    <SignedOut>
      <SignIn
        path="/login"
        routing="path"
        afterSignInUrl="/"
      />
    </SignedOut>
  );
}

// Clerk sign-up page component
export function ClerkSignUpPage() {
  const { isSignedIn, getToken } = useAuth();
  const { user } = useUser();
  const navigate = useCustomNavigate();
  const [processed, setProcessed] = useState(false);
  const { mutateAsync: logout } = useLogout();
  const { signOut } = useClerk();

  useEffect(() => {
    async function handleSignup() {
      if (isSignedIn && user && !processed) {
        console.log("[ClerkSignUpPage] User is signed in, processing sign up...");
        setProcessed(true);
        const token = await getToken();
        if (token) {
          const username =
            user.username || user.primaryEmailAddress?.emailAddress || user.id;
          console.log(`[ClerkSignUpPage] Creating Langflow user for: ${username}`);
          await ensureLangflowUser(token, username);
        } else {
          console.log("[ClerkSignUpPage] No token received from Clerk.");
        }
        console.log("[ClerkSignUpPage] Signing out user after sign up.");
        await logout();
        console.log("[ClerkSignUpPage] Redirecting to /login after sign up.");
        navigate("/login");
      }
    }
    handleSignup();
  }, [isSignedIn, user, getToken, logout, navigate, processed]);

  return (
    <SignedOut>
      <SignUp
        path="/sign-up"
        routing="path"
        afterSignUpUrl="/login"
      />
    </SignedOut>
  );
}

// Original pages
import OriginalLoginPage from "../pages/LoginPage";
import OriginalSignUp from "../pages/SignUpPage";
const OriginalLoginAdminPage = lazy(() => import("../pages/AdminPage/LoginPage"));

export const LoginPage = IS_CLERK_AUTH ? ClerkLoginPage : OriginalLoginPage;
export const SignUpPage = IS_CLERK_AUTH ? ClerkSignUpPage : OriginalSignUp;
export const LoginAdminPage = IS_CLERK_AUTH ? ClerkLoginPage : OriginalLoginAdminPage;

