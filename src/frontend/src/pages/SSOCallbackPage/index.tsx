import { useContext, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AuthContext } from "../../contexts/authContext";
import useAlertStore from "../../stores/alertStore";
import { api } from "../../controllers/API/api";
import { getURL } from "../../controllers/API/helpers/constants";
import { useQueryClient } from "@tanstack/react-query";

export default function SSOCallbackPage(): JSX.Element {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login, clearAuthSession } = useContext(AuthContext);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const queryClient = useQueryClient();
  const [isProcessing, setIsProcessing] = useState(true);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Get the authorization code and state from URL params
        const code = searchParams.get("code");
        const state = searchParams.get("state");
        const error = searchParams.get("error");
        const errorDescription = searchParams.get("error_description");

        // Check for OAuth errors
        if (error) {
          throw new Error(errorDescription || error);
        }

        if (!code || !state) {
          throw new Error("Missing authorization code or state parameter");
        }

        // Exchange the code for tokens
        const response = await api.get(
          `${getURL("SSO_CALLBACK")}?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
        );

        const { access_token, refresh_token } = response.data;

        // Clear any existing session and log in with new tokens
        clearAuthSession();
        login(access_token, "sso", refresh_token);
        queryClient.clear();

        // Redirect to home page
        navigate("/");
      } catch (error: any) {
        console.error("SSO callback error:", error);
        setErrorData({
          title: "SSO Authentication Failed",
          list: [
            error?.response?.data?.detail ||
              error?.message ||
              "Failed to complete SSO authentication",
          ],
        });
        // Redirect back to login page on error
        setTimeout(() => navigate("/login"), 3000);
      } finally {
        setIsProcessing(false);
      }
    };

    handleCallback();
  }, [
    searchParams,
    navigate,
    login,
    clearAuthSession,
    setErrorData,
    queryClient,
  ]);

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-muted">
      <div className="flex flex-col items-center gap-4">
        {isProcessing ? (
          <>
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary border-t-transparent"></div>
            <p className="text-lg text-foreground">Completing sign in...</p>
            <p className="text-sm text-muted-foreground">
              Please wait while we authenticate your account
            </p>
          </>
        ) : (
          <>
            <p className="text-lg text-foreground">Authentication complete</p>
            <p className="text-sm text-muted-foreground">Redirecting...</p>
          </>
        )}
      </div>
    </div>
  );
}
