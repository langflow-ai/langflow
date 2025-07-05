import { SignUp, useAuth, useUser, useClerk } from "@clerk/clerk-react";
import { useEffect, useState } from "react";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { ensureLangflowUser } from "@/clerk/langflow-sync";

export default function ClerkSignUpPage() {
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
            user.username ||
            user.primaryEmailAddress?.emailAddress ||
            user.id;
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
