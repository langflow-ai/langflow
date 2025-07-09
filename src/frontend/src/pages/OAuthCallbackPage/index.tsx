import { useContext, useEffect, useState } from "react";
import { Cookies } from "react-cookie";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "../../components/ui/button";
import {
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_REFRESH_TOKEN,
} from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";

export default function OAuthCallbackPage(): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login } = useContext(AuthContext);

  useEffect(() => {
    const handleOAuthCallback = async () => {
      try {
        const success = searchParams.get("success");
        const error = searchParams.get("error");

        if (error) {
          setError("OAuth authentication failed. Please try again.");
          setIsLoading(false);
          return;
        }

        if (success) {
          // Check if authentication cookies are present
          const cookies = new Cookies();
          const accessToken = cookies.get(LANGFLOW_ACCESS_TOKEN);
          const refreshToken = cookies.get(LANGFLOW_REFRESH_TOKEN);

          if (accessToken) {
            // Call login function just like the regular login page does
            // This will handle setting up the auth state and redirecting
            login(accessToken, "oauth", refreshToken);

            // The AuthContext will handle the redirect automatically
            // No need to manually navigate
          } else {
            setError(
              "Authentication cookies not found. Please try logging in again.",
            );
            setIsLoading(false);
          }
        } else {
          setError("Invalid OAuth callback. Please try again.");
          setIsLoading(false);
        }
      } catch (err) {
        setError("OAuth authentication failed. Please try again.");
        setIsLoading(false);
      }
    };

    handleOAuthCallback();
  }, [navigate, login, searchParams]);

  if (error) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-muted">
        <div className="flex w-72 flex-col items-center justify-center gap-2">
          <div className="text-center">
            <h2 className="mb-2 text-xl font-semibold text-destructive">
              Authentication Error
            </h2>
            <p className="mb-4 text-muted-foreground">{error}</p>
            <Button onClick={() => navigate("/login")}>Back to Login</Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-muted">
      <div className="flex w-72 flex-col items-center justify-center gap-2">
        <div className="text-center">
          <h2 className="mb-2 text-xl font-semibold">
            Completing Authentication...
          </h2>
          <p className="text-muted-foreground">Please wait.</p>
        </div>
      </div>
    </div>
  );
}
