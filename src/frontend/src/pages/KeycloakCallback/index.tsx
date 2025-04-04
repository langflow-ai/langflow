/**
 * @file KeycloakCallback/index.tsx
 * @description Component for handling the Keycloak/OpenID Connect callback after SSO authentication.
 * Displayed when users are redirected back from Keycloak with an authorization code.
 * Shows a loading spinner while processing the authentication.
 */
import { useKeycloakAuth } from "@/hooks/useKeycloakAuth";
import { useEffect } from "react";

/**
 * Keycloak callback handler component.
 *
 * This component is rendered when the user is redirected back from Keycloak
 * after a successful authentication. It handles the OAuth callback flow,
 * exchanging the authorization code for access tokens, and then redirects
 * the user to the application's main page.
 */
export default function KeycloakCallback() {
  // Get the callback handler and loading state from the hook
  const { handleKeycloakCallback, isLoading } = useKeycloakAuth();

  // Once the Keycloak configuration is loaded, process the callback
  useEffect(() => {
    if (!isLoading) {
      handleKeycloakCallback();
    }
  }, [isLoading, handleKeycloakCallback]);

  // Display a loading spinner while processing the authentication
  return (
    <div className="flex h-screen w-full items-center justify-center">
      <div className="flex flex-col items-center justify-center">
        <div className="h-16 w-16 animate-spin rounded-full border-b-2 border-t-2 border-primary"></div>
        <p className="mt-4 text-lg">Logging you in...</p>
      </div>
    </div>
  );
}
