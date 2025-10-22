/**
 * AuthBroadcastListener Component
 * 
 * Listens for authentication events from other tabs via BroadcastChannel.
 * When another tab logs out, this component:
 * 1. Immediately cancels all ongoing React Query requests
 * 2. Clears all cached query data
 * 3. Signs out from Clerk (if enabled)
 * 4. Clears authentication state
 * 5. Redirects to login page
 * 
 * This prevents the CPU spike caused by infinite query retries.
 */

import { IS_CLERK_AUTH } from "@/clerk/auth";
import { useClerk } from "@clerk/clerk-react";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAuthStore from "@/stores/authStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useFolderStore } from "@/stores/foldersStore";
import { authBroadcast } from "@/utils/auth-broadcast";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect } from "react";
import { useLocation } from "react-router-dom";

export function AuthBroadcastListener() {
  const queryClient = useQueryClient();
  const navigate = useCustomNavigate();
  const location = useLocation();
  const logout = useAuthStore((state) => state.logout);
  const { signOut } = IS_CLERK_AUTH ? useClerk() : { signOut: async () => {} };

  /**
   * Handle logout event from another tab
   * This runs when ANY other tab calls logout
   */
  const handleCrossTabLogout = useCallback(async () => {
    const currentPath = location.pathname;

    // Don't process if already on login page
    if (currentPath.includes("login")) {
      console.debug("[AuthBroadcast] Already on login page, ignoring logout event");
      return;
    }

    // Special handling for root path "/" - it's a public page
    const isOnRootPath = currentPath === "/";

    console.log("[AuthBroadcast] Logout event received from another tab", {
      currentPath,
      isOnRootPath,
    });

    try {
      // 1. IMMEDIATELY cancel all ongoing queries to prevent retries
      console.debug("[AuthBroadcast] Cancelling all queries...");
      await queryClient.cancelQueries();

      // 2. Clear all query cache
      console.debug("[AuthBroadcast] Clearing query cache...");
      queryClient.clear();

      // 3. Reset store states
      console.debug("[AuthBroadcast] Resetting stores...");
      useFlowStore.getState().resetFlowState();
      useFlowsManagerStore.getState().resetStore();
      useFolderStore.getState().resetStore();

      // 4. Clear auth state (without calling backend)
      console.debug("[AuthBroadcast] Clearing auth state...");
      await logout();

      // 5. For root path "/", stay on the page (just update auth state)
      if (isOnRootPath) {
        console.debug("[AuthBroadcast] On root path, staying at / (UI will update to show Login/Book Demo)");
        // Sign out from Clerk in background (best effort, don't block)
        // If this fails, the login page will detect and clean up stale session
        if (IS_CLERK_AUTH && signOut) {
          signOut().catch((error) => {
            console.debug("[AuthBroadcast] Clerk signOut failed (will be cleaned up on next login):", error);
          });
          console.debug("[AuthBroadcast] Clerk signOut initiated (background)");
        }
        console.log("[AuthBroadcast] Cross-tab logout completed - staying at /");
        return;
      }

      // 6. For protected pages, redirect IMMEDIATELY (don't wait for Clerk)
      if (IS_CLERK_AUTH && signOut) {
        console.debug("[AuthBroadcast] Redirecting to /login immediately...");
        // Navigate first (instant)
        navigate("/login", { replace: true });
        // Then sign out from Clerk in background (best effort)
        // If this fails, the login page will detect and clean up stale session
        signOut().catch((error) => {
          console.debug("[AuthBroadcast] Clerk signOut failed (will be cleaned up on next login):", error);
        });
        console.debug("[AuthBroadcast] Clerk signOut initiated (background)");
        return;
      }

      // 7. Redirect to login (for non-Clerk auth)
      console.debug("[AuthBroadcast] Redirecting to login...");
      navigate("/login", { replace: true });

      console.log("[AuthBroadcast] Cross-tab logout completed successfully");
    } catch (error) {
      console.error("[AuthBroadcast] Error during cross-tab logout:", error);
      // Force redirect even if cleanup fails (but not for root path)
      if (!isOnRootPath) {
        navigate("/login", { replace: true });
      }
    }
  }, [location.pathname, queryClient, logout, navigate, signOut]);

  useEffect(() => {
    // Only run on client side
    if (typeof window === 'undefined') {
      return;
    }

    // Register listener for logout events from other tabs
    try {
      const unsubscribe = authBroadcast.onLogout(() => {
        handleCrossTabLogout();
      });

      // Cleanup on unmount
      return () => {
        unsubscribe();
      };
    } catch (error) {
      console.error("[AuthBroadcast] Failed to register listener:", error);
      // Return empty cleanup function if registration fails
      return () => {};
    }
  }, [handleCrossTabLogout]);

  // This component doesn't render anything
  return null;
}
