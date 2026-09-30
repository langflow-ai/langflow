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
