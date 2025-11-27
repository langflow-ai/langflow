import { useContext, useMemo } from "react";
import { envConfig } from "@/config/env";
import KeycloakService from "@/services/keycloak";
import { AuthContext } from "@/contexts/authContext";

export function CustomProfileIcon() {
  const { userData } = useContext(AuthContext);

  const initials = useMemo(() => {
    // Prefer Keycloak-derived initials when enabled
    if (envConfig.keycloakEnabled) {
      try {
        const info = KeycloakService.getInstance().getUserInfo();
        if (info) {
          const first = (info.firstName || "").trim();
          const last = (info.lastName || "").trim();
          if (first || last) {
            return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
          }
          const username = (info.username || "").trim();
          if (username) {
            const parts = username.split(/[\s._-]+/).filter(Boolean);
            if (parts.length >= 2) {
              return `${parts[0].charAt(0)}${parts[1].charAt(0)}`.toUpperCase();
            }
            return username.slice(0, 2).toUpperCase();
          }
        }
      } catch {
        // ignore and fallback
      }
    }

    // Fallback to AuthContext userData if available
    if (userData) {
      console.log("userData", userData);
      const username = (userData.username || "").trim();
      if (username) {
        const parts = username.split(/[\s._-]+/).filter(Boolean);
        if (parts.length >= 2) {
          return `${parts[0].charAt(0)}${parts[1].charAt(0)}`.toUpperCase();
        }
        return username.slice(0, 2).toUpperCase();
      }
    }

    // Default placeholder
    return "U";
  }, [userData]);

  // Always display initials
  return (
    <div className="flex h-full w-full items-center justify-center rounded-full text-white text-xs font-medium">
      {initials}
    </div>
  );
}

export default CustomProfileIcon;
