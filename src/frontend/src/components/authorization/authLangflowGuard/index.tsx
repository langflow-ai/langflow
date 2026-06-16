import { useContext } from "react";
import { AuthContext } from "@/contexts/authContext";
import { CustomNavigate } from "@/customization/components/custom-navigate";
import { LoadingPage } from "@/pages/LoadingPage";
import useAuthStore from "@/stores/authStore";

/**
 * Gates the legacy Langflow surface — the visual builder (`/flows`,
 * `/components`, `/all`, `/mcp`, `/assets`, `/flow/:id`), the playground, and
 * most of `/settings` — to superusers only.
 *
 * Lothal is a distinct product built on top of Langflow; regular users only
 * ever interact with the Lothal pages. A non-admin who lands on a Langflow
 * route (typed URL, stale bookmark, etc.) is redirected to their Lothal home
 * at `/lothal`. Admins keep full access so we can keep adapting the Langflow
 * features incrementally rather than ripping them out. Auto-login / dev
 * deployments run as the implicit default superuser and also keep full access.
 *
 * Scope: this is a UI boundary only. The Langflow REST API is still reachable
 * with any authenticated user's token — locking those endpoints down to
 * superusers is a separate, deliberate backend change.
 */
export const ProtectedLangflowRoute = ({ children }) => {
  const { userData } = useContext(AuthContext);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const autoLogin = useAuthStore((state) => state.autoLogin);
  const isAdmin = useAuthStore((state) => state.isAdmin);

  // Superuser — or the implicit superuser in auto-login/dev mode — gets the
  // full Langflow surface.
  if (isAdmin || autoLogin === true) {
    return children;
  }

  // Still resolving who the caller is (whoami in flight): show the loader
  // rather than flashing a premature redirect for an admin mid-load.
  if (!isAuthenticated || !userData) {
    return <LoadingPage />;
  }

  // Authenticated Lothal user with no admin rights → send them home.
  return <CustomNavigate to="/lothal" replace />;
};
