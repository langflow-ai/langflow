import { SignIn, SignedIn, SignedOut, useAuth } from "@clerk/clerk-react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useCookies } from "react-cookie";
import { LANDING_BASENAME } from "./landingRoutes";
import {
  clearStoredOrgSelection,
  hasWorkspaceSession,
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_REFRESH_TOKEN,
} from "./session";

export default function NewLandingPageLogin() {
  const { isSignedIn, isLoaded } = useAuth();
  const navigate = useNavigate();
  const [cookies] = useCookies([LANGFLOW_ACCESS_TOKEN, LANGFLOW_REFRESH_TOKEN]);

  console.log("[NewLandingPageLogin] render", { isLoaded, isSignedIn });

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      clearStoredOrgSelection();
    }
  }, [isLoaded, isSignedIn]);

  useEffect(() => {
    if (isLoaded && isSignedIn) {
      const workspaceReady = hasWorkspaceSession(cookies);
      const destination = workspaceReady ? "/flows" : "/organization";

      console.log(
        "[NewLandingPageLogin] User signed in, redirecting based on session",
        { workspaceReady, destination },
      );

      if (workspaceReady) {
        window.location.assign("/flows");
        return;
      }

      navigate(destination, { replace: true });
    }
  }, [cookies, isLoaded, isSignedIn, navigate]);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "1rem",
      }}
    >
      <div>
        <SignedOut>
          <SignIn
            afterSignInUrl={`${LANDING_BASENAME}/login`}
            redirectUrl={`${LANDING_BASENAME}/login`}
          />
        </SignedOut>
        <SignedIn>
          <div style={{ textAlign: "center" }}>Redirecting you to your organization list…</div>
        </SignedIn>
      </div>
    </div>
  );
}