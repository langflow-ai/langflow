import { SignIn, SignUp as ClerkSignUp, useAuth, useUser , useClerk, SignedOut} from "@clerk/clerk-react";
import { lazy, useEffect, useState } from "react";
import { useLogout } from "./auth";
import { IS_CLERK_AUTH } from "@/clerk/auth";
// Clerk login page component
export function ClerkLoginPage() {
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

