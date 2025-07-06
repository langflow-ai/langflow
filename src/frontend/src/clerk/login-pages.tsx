import { lazy } from "react";
import { SignIn, SignUp, useAuth, useUser, useClerk } from "@clerk/clerk-react";
import { useEffect, useState } from "react";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import {
  IS_CLERK_AUTH,
  ensureLangflowUser,
} from "./auth";

// Clerk login page component
export function ClerkLoginPage() {
  return <SignIn />;
}

// Clerk sign-up page component
export function ClerkSignUpPage() {
  const { isSignedIn, getToken } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();
  const navigate = useCustomNavigate();
  const [processed, setProcessed] = useState(false);

  useEffect(() => {
    async function handleSignup() {
      if (isSignedIn && user && !processed) {
        setProcessed(true);
        const token = await getToken();
        if (token) {
          const username =
            user.username || user.primaryEmailAddress?.emailAddress || user.id;
          await ensureLangflowUser(token, username);
        }
        await signOut();
        navigate("/login");
      }
    }
    handleSignup();
  }, [isSignedIn, user, getToken, signOut, navigate, processed]);

  return <SignUp />;
}

// Original pages
import OriginalLoginPage from "../pages/LoginPage";
import OriginalSignUp from "../pages/SignUpPage";
const OriginalLoginAdminPage = lazy(() => import("../pages/AdminPage/LoginPage"));

export const LoginPage = IS_CLERK_AUTH ? ClerkLoginPage : OriginalLoginPage;
export const SignUpPage = IS_CLERK_AUTH ? ClerkSignUpPage : OriginalSignUp;
export const LoginAdminPage = IS_CLERK_AUTH ? ClerkLoginPage : OriginalLoginAdminPage;

export const SignUp = SignUpPage; // maintain previous named export
