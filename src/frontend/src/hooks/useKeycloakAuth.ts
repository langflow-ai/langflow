/**
 * @file useKeycloakAuth.ts
 * @description Hook for handling Keycloak/OpenID Connect SSO authentication in Langflow.
 * Provides functions to initiate login flow, handle callbacks, and expose configuration.
 */
import { BASE_URL_API } from "@/constants/constants";
import { AuthContext } from "@/contexts/authContext";
import axios from "axios";
import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

/**
 * Keycloak configuration interface that matches the backend schema.
 * Contains all the necessary properties for OpenID Connect authentication.
 */
type KeycloakConfig = {
  /** Whether Keycloak authentication is enabled */
  enabled: boolean;
  /** Base URL of the Keycloak server */
  serverUrl: string;
  /** Keycloak realm name */
  realm: string;
  /** Client ID registered in Keycloak */
  clientId: string;
  /** URI where Keycloak will redirect after authentication */
  redirectUri: string;
  /** Whether to force SSO-only login (hide username/password form) */
  forceSSO?: boolean;
};

/**
 * Custom hook that handles Keycloak/OpenID Connect authentication flow.
 *
 * @returns Various properties and functions for Keycloak integration:
 *  - keycloakConfig: The raw configuration object from the server
 *  - isLoading: Whether the configuration is still loading
 *  - redirectToKeycloakLogin: Function to initiate the login flow
 *  - handleKeycloakCallback: Function to handle the OAuth callback
 *  - isKeycloakEnabled: Whether Keycloak is enabled
 *  - isForceSSO: Whether to hide the username/password login form
 */
export const useKeycloakAuth = () => {
  const [keycloakConfig, setKeycloakConfig] = useState<KeycloakConfig | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();
  const { login } = useContext(AuthContext);

  // Fetch the Keycloak configuration from the backend when the component mounts
  useEffect(() => {
    // Fetch Keycloak configuration from the backend
    axios
      .get(`${BASE_URL_API}keycloak/config`)
      .then((response) => {
        setKeycloakConfig(response.data);
        setIsLoading(false);
      })
      .catch((error) => {
        console.error("Failed to fetch Keycloak config:", error);
        setIsLoading(false);
      });
  }, []);

  /**
   * Extracts the authorization code from the URL query parameters.
   * Used during the callback phase of OAuth flow.
   *
   * @returns The 'code' parameter from the URL or null if not present
   */
  const getAuthCodeFromUrl = (): string | null => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get("code");
  };

  /**
   * Generates a cryptographically secure random string.
   * Used for CSRF protection (state parameter) in the OAuth flow.
   *
   * @returns Hexadecimal string with 128 bits of entropy
   */
  const generateRandomString = () => {
    const array = new Uint32Array(4); // 4 * 32 = 128 bit entropy
    window.crypto.getRandomValues(array); // Fill the array with random values
    return Array.from(array, (num) => num.toString(16).padStart(8, "0")).join(
      "",
    );
  };

  /**
   * Initiates the Keycloak login flow by redirecting to the Keycloak server.
   * Generates a state parameter for CSRF protection.
   */
  const redirectToKeycloakLogin = () => {
    if (!keycloakConfig?.enabled) {
      console.error("Keycloak is not enabled or configuration is missing");
      return;
    }

    // Generate a random state for CSRF protection
    const state = generateRandomString();
    const nonce = generateRandomString();

    sessionStorage.setItem("keycloak_state", state);
    sessionStorage.setItem("keycloak_nonce", nonce);

    // Build the authorization URL with required OAuth parameters
    const authUrl = new URL(
      `${keycloakConfig.serverUrl}/realms/${keycloakConfig.realm}/protocol/openid-connect/auth`,
    );
    authUrl.searchParams.append("client_id", keycloakConfig.clientId);
    authUrl.searchParams.append(
      "redirect_uri",
      `${keycloakConfig.redirectUri}`,
    );
    authUrl.searchParams.append("response_type", "code");
    authUrl.searchParams.append("scope", "openid email profile offline_access");
    authUrl.searchParams.append("state", state);
    authUrl.searchParams.append("nonce", nonce);

    // Redirect to Keycloak login page
    window.location.href = authUrl.toString();
  };

  /**
   * Handles the callback from Keycloak after successful authentication.
   * Validates the state parameter to prevent CSRF attacks.
   * Exchanges the authorization code for tokens.
   */
  const handleKeycloakCallback = async () => {
    const authCode = getAuthCodeFromUrl();

    // Verify the state parameter to prevent CSRF attacks
    const storedState = sessionStorage.getItem("keycloak_state");
    const storedNonce = sessionStorage.getItem("keycloak_nonce");
    const urlParams = new URLSearchParams(window.location.search);
    const returnedState = urlParams.get("state");

    // Validate state to prevent CSRF attacks
    if (!authCode || !storedState || storedState !== returnedState) {
      console.error("Invalid authorization response");
      navigate("/login");
      return;
    }

    try {
      // Exchange the code for tokens via the backend endpoint
      const response = await axios.get(`${BASE_URL_API}keycloak/callback`, {
        params: { code: authCode, nonce: storedNonce },
      });

      // Use the Langflow tokens for authentication
      login(response.data.access_token, "login", response.data.refresh_token);

      // Clean up the session storage and redirect to home
      sessionStorage.removeItem("keycloak_state");
      sessionStorage.removeItem("keycloak_nonce");
      navigate("/flows");
    } catch (error) {
      console.error("Failed to exchange code for token:", error);
      navigate("/login");
    }
  };

  // Return relevant properties and functions for the consuming component
  return {
    keycloakConfig,
    isLoading,
    redirectToKeycloakLogin,
    handleKeycloakCallback,
    isKeycloakEnabled: keycloakConfig?.enabled || false,
    isForceSSO: keycloakConfig?.forceSSO || false,
  };
};
