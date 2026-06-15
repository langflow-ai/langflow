import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

const REDIRECT_SESSION_KEY = "langflow_login_redirect";

export function useSanitizeRedirectUrl() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    if (searchParams.has("redirect")) {
      const redirectPath = searchParams.get("redirect");
      if (redirectPath) {
        sessionStorage.setItem(REDIRECT_SESSION_KEY, redirectPath);
      }
      navigate(window.location.pathname, { replace: true });
    }
  }, []);
}

export function consumeRedirectUrl(): string | null {
  const redirectPath = sessionStorage.getItem(REDIRECT_SESSION_KEY);
  if (redirectPath) {
    sessionStorage.removeItem(REDIRECT_SESSION_KEY);
  }
  return redirectPath;
}

/**
 * Stash a post-login destination so the auth guards' `consumeRedirectUrl()`
 * picks it up after sign-in. Used by the Lothal login page to default to the
 * projects page instead of the shared `/flows` fallback.
 */
export function setRedirectUrl(redirectPath: string): void {
  sessionStorage.setItem(REDIRECT_SESSION_KEY, redirectPath);
}
