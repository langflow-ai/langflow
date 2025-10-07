import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

export function useSanitizeRedirectUrl() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    if (searchParams.has("redirect")) {
      navigate(window.location.pathname, { replace: true });
    }
  }, []);
}
