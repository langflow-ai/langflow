import {
  OrganizationList,
  SignedIn,
  SignedOut,
  useAuth,
  useClerk,
  useOrganization,
  useUser,
} from "@clerk/clerk-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Navigate,
  useSearchParams,
} from "react-router-dom";
import { useCookies } from "react-cookie";
import { LANDING_BASENAME } from "./landingRoutes";
import logoicon from "./new-assets/visualailogo.png";
import ProgressBar from "./ProgressBar";
import {
  ACTIVE_ORG_STORAGE_KEY,
  LANGFLOW_ACCESS_TOKEN,
  LANGFLOW_REFRESH_TOKEN,
  ORG_SELECTED_KEY,
} from "./session";
/**
 * ==========
 * Constants
 * ==========
 */
const CLERK_DUMMY_PASSWORD = "clerk_dummy_password";
const LANGFLOW_AUTO_LOGIN_OPTION = "auto_login_lf";

const API_BASE = (import.meta.env.VITE_LANGFLOW_API_BASE ?? "/api/v1/")
  .replace(/\/?$/, "/");

/**
 * ==========
 * HTTP helper
 * ==========
 */
class HttpError extends Error {
  status: number;
  data: Record<string, any> | null;

  constructor(status: number, message: string, data: Record<string, any> | null) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

function apiUrl(path: string) {
  return `${API_BASE}${path.replace(/^\/+/, "")}`;
}

async function requestJson(
  path: string,
  {
    method = "GET",
    headers = {},
    body,
    token,
    expectJson = true,
  }: {
    method?: string;
    headers?: Record<string, string>;
    body?: BodyInit | null;
    token?: string;
    expectJson?: boolean;
  } = {},
) {
  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };

  if (body && !(body instanceof FormData) && !headers["Content-Type"]) {
    finalHeaders["Content-Type"] =
      body instanceof URLSearchParams
        ? "application/x-www-form-urlencoded"
        : "application/json";
  }

  if (token) {
    finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(apiUrl(path), {
    method,
    headers: finalHeaders,
    body: body ?? undefined,
  });

  const text = expectJson ? await response.text() : null;
  let data: Record<string, any> | null = null;

  if (text) {
    try {
      data = JSON.parse(text) as Record<string, any>;
    } catch {
      // Non-JSON response (e.g., HTML error page); keep text for fallback messaging
      data = null;
    }
  }

  if (!response.ok) {
    const detail =
      (data?.detail as string) ??
      (text ? text.slice(0, 200) : null) ??
      response.statusText;
    throw new HttpError(response.status, detail || "Request failed", data);
  }

  return data;
}

/**
 * ==========
 * Backend helpers (local clone of old behavior)
 * ==========
 */

async function fetchWhoAmI(token: string) {
  return requestJson("users/whoami", { token });
}

async function ensureLangflowUser(
  token: string,
  username: string,
  maxRetries: number = 2,
): Promise<{ justCreated: boolean; user: Record<string, any> | null }> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const user = await fetchWhoAmI(token);
      return { justCreated: false, user };
    } catch (error: any) {
      if (error instanceof HttpError && error.status === 401) {
        // User missing → try to create
        try {
          await requestJson("users/", {
            method: "POST",
            token,
            body: JSON.stringify({
              username,
              password: CLERK_DUMMY_PASSWORD,
            }),
          });
          return { justCreated: true, user: null };
        } catch (createError: any) {
          // Handle race condition: "username is unavailable"
          if (
            createError instanceof HttpError &&
            createError.status === 400 &&
            typeof createError.data?.detail === "string" &&
            createError.data.detail.includes("username is unavailable")
          ) {
            // Small delay then retry whoami
            await new Promise((resolve) => setTimeout(resolve, 100));
            continue;
          }
          throw createError;
        }
      }
      throw error;
    }
  }
  throw new Error("[ensureLangflowUser] Max retries exceeded");
}

async function backendLogin(username: string, token: string) {
  return requestJson("login", {
    method: "POST",
    token,
    body: new URLSearchParams({
      username,
      password: CLERK_DUMMY_PASSWORD,
    }),
  });
}

async function createOrganisation(token: string) {
  try {
    await requestJson("create_organisation", {
      method: "POST",
      token,
    });
  } catch (error: any) {
    // Some backends return 200 or 400 when org already exists
    if (
      error instanceof HttpError &&
      (error.status === 200 || error.status === 400)
    ) {
      return;
    }
    throw error;
  }
}

/**
 * ==========
 * Active org storage (local clone)
 * ==========
 */

function setStoredActiveOrgId(orgId: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (orgId) {
      localStorage.setItem(ACTIVE_ORG_STORAGE_KEY, orgId);
    } else {
      localStorage.removeItem(ACTIVE_ORG_STORAGE_KEY);
    }
  } catch (error) {
    console.warn("[activeOrgStorage] Unable to persist active org", error);
  }
}

/**
 * ==========
 * Main component
 * ==========
 */

export default function OrganizationOnboarding() {
  const { isSignedIn, isLoaded, getToken } = useAuth();
  const { signOut } = useClerk();
  const { organization } = useOrganization();
  const { user } = useUser();

  console.log("[OrganizationOnboarding] render", {
    isSignedIn,
    organizationId: organization?.id,
  });

  const [searchParams, setSearchParams] = useSearchParams();

  const [cookies, setCookie, removeCookie] = useCookies([
    LANGFLOW_ACCESS_TOKEN,
    LANGFLOW_REFRESH_TOKEN,
    LANGFLOW_AUTO_LOGIN_OPTION,
  ]);

  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(false);

  const bootstrappedRef = useRef(false);
  const processedOrgRef = useRef<string | null>(null);
  const provisioningOrgRef = useRef<string | null>(null);

  /**
   * Derived user info for display
   */
  const displayName =
    user?.fullName ||
    user?.username ||
    user?.primaryEmailAddress?.emailAddress ||
    "Current member";

  const emailAddress =
    user?.primaryEmailAddress?.emailAddress ||
    user?.emailAddresses?.[0]?.emailAddress ||
    "";

  const avatarUrl = user?.imageUrl;
  const initials = displayName
    .split(" ")
    .map((segment) => segment[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const isMobile = typeof window !== "undefined" && window.innerWidth < 640;

  const showLoadingOverlay = isBootstrapping;

  const hasExistingOrgSelection = useMemo(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(ORG_SELECTED_KEY) === "true";
  }, []);

  /**
   * Persist session like old component (cookies + storage)
   * This is what the main app /flows logic expects.
   */
  const persistSession = useCallback(
    (accessToken: string, refreshToken: string | null, activeOrgId: string) => {
      const cookieOptions = { path: "/", sameSite: "lax" as const };

      setCookie(LANGFLOW_ACCESS_TOKEN, accessToken, cookieOptions);
      setCookie(LANGFLOW_AUTO_LOGIN_OPTION, "login", cookieOptions);

      if (refreshToken) {
        setCookie(LANGFLOW_REFRESH_TOKEN, refreshToken, cookieOptions);
      }

      localStorage.setItem(ORG_SELECTED_KEY, "true");
      setStoredActiveOrgId(activeOrgId);

      console.log("[OrganizationOnboarding] Session persisted", {
        hasAccessToken: Boolean(accessToken),
        hasRefreshToken: Boolean(refreshToken),
        activeOrgId,
      });
    },
    [setCookie],
  );

  const clearSession = useCallback(async () => {
    removeCookie(LANGFLOW_ACCESS_TOKEN, { path: "/" });
    removeCookie(LANGFLOW_REFRESH_TOKEN, { path: "/" });
    removeCookie(LANGFLOW_AUTO_LOGIN_OPTION, { path: "/" });
    localStorage.removeItem(ORG_SELECTED_KEY);
    setStoredActiveOrgId(null);

    try {
      await signOut();
    } catch {
      // ignore logout errors
    }
  }, [removeCookie, signOut]);

  const goToFlows = useCallback(() => {
    console.log("[OrganizationOnboarding] Redirecting to /flows");
    window.location.assign("/flows");
  }, []);

  /**
   * Core bootstrap flow:
   * - createOrganisation
   * - ensureLangflowUser
   * - backendLogin
   * - persist cookies + storage
   * - redirect to /flows
   */
  const bootstrapSession = useCallback(async () => {
    if (!isSignedIn || !organization?.id || bootstrappedRef.current) return;

    setError(null);
    setStatus("Preparing your workspace...");
    setIsBootstrapping(true);
    bootstrappedRef.current = true;

    const activeOrgId = organization.id;

    try {
      setStatus("Requesting Clerk token...");
      const orgToken = await getToken();
      if (!orgToken) {
        throw new Error("Unable to retrieve Clerk session token");
      }

      const username =
        user?.username ||
        user?.primaryEmailAddress?.emailAddress ||
        user?.id ||
        "clerk_user";

      console.log("[OrganizationOnboarding] Calling createOrganisation()");
      setStatus("Ensuring organization exists...");
      await createOrganisation(orgToken);
      console.log("[OrganizationOnboarding] createOrganisation() completed");

      console.log("[OrganizationOnboarding] Calling ensureLangflowUser()");
      setStatus("Synchronizing user profile...");
      await ensureLangflowUser(orgToken, username);
      console.log("[OrganizationOnboarding] ensureLangflowUser() completed");

      console.log("[OrganizationOnboarding] Calling backendLogin()");
      setStatus("Creating backend session...");
      const tokens = await backendLogin(username, orgToken);
      console.log("[OrganizationOnboarding] backendLogin() succeeded");

      persistSession(orgToken, (tokens as any)?.refresh_token ?? null, activeOrgId);

      setStatus("Redirecting to workspace...");
      console.log(
        "[OrganizationOnboarding] Redirecting to workspace with org",
        activeOrgId,
      );
      goToFlows();
    } catch (err: any) {
      console.error("[OrganizationOnboarding] Failed to bootstrap", err);
      const msg =
        err instanceof Error && err.message
          ? err.message
          : "Authentication failed";
      setError(msg);
      bootstrappedRef.current = false;
      await clearSession();
    } finally {
      setIsBootstrapping(false);
      setStatus(null);
    }
  }, [
    clearSession,
    getToken,
    isSignedIn,
    organization?.id,
    persistSession,
    user,
    goToFlows,
  ]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn || !organization?.id) return;
    if (!hasExistingOrgSelection || bootstrappedRef.current) return;

    console.log(
      "[OrganizationOnboarding] Existing org selection detected; bootstrapping",
    );

    bootstrapSession();
  }, [
    bootstrapSession,
    hasExistingOrgSelection,
    isLoaded,
    isSignedIn,
    organization?.id,
  ]);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    const orgSelected = localStorage.getItem(ORG_SELECTED_KEY) === "true";
    const activeOrgId = localStorage.getItem(ACTIVE_ORG_STORAGE_KEY);
    const hasAccessToken = Boolean(cookies[LANGFLOW_ACCESS_TOKEN]);

    if (orgSelected && activeOrgId && hasAccessToken) {
      console.log("[OrganizationOnboarding] Session already present; routing to /flows", {
        activeOrgId,
      });
      goToFlows();
    }
  }, [cookies, goToFlows, isLoaded, isSignedIn]);

  /**
   * When Clerk redirects back with ?selected=true,
   * create org + bootstrap session, then go to /flows.
   */
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    const selected = searchParams.get("selected") === "true";
    if (!selected || !organization?.id) return;

    console.log("[OrganizationOnboarding] Detected ?selected=true for org", {
      organizationId: organization.id,
    });

    if (
      processedOrgRef.current === organization.id ||
      provisioningOrgRef.current === organization.id
    ) {
      return;
    }

    setStatus("Preparing your workspace...");
    setIsBootstrapping(true);
    provisioningOrgRef.current = organization.id;

    (async () => {
      try {
        processedOrgRef.current = organization.id;
        await bootstrapSession();
      } finally {
        provisioningOrgRef.current = null;
        const next = new URLSearchParams(searchParams);
        next.delete("selected");
        setSearchParams(next);
      }
    })().catch((err) => {
      console.error("[OrganizationOnboarding] bootstrap wrapper failed", err);
      bootstrappedRef.current = false;
    });
  }, [
    bootstrapSession,
    isLoaded,
    isSignedIn,
    organization?.id,
    searchParams,
    setSearchParams,
  ]);

  /**
   * If not signed in, send to new landing login route.
   */
  if (!isLoaded) {
    console.log(
      "[OrganizationOnboarding] Clerk not loaded yet; waiting before routing",
    );
    return null;
  }

  if (!isSignedIn) {
    console.log(
      "[OrganizationOnboarding] User not signed in, redirecting to /login",
    );
    return <Navigate to="/login" replace />;
  }

  return (
    <>
      {showLoadingOverlay && (
        <div className="loading-overlay" role="status" aria-live="polite">
          <div className="loading-card">
            <div className="loading-title">Setting up things for you</div>
            <ProgressBar remSize={18} />
          </div>
        </div>
      )}

      <div
        style={{
          display: "grid",
          placeItems: isMobile ? "start center" : "center",
          alignContent: "center",
          minHeight: "100vh",
          width: "100%",
          padding: isMobile ? "3rem 1.25rem" : "2rem",
          backgroundColor: "#f8fafc",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: "480px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "1.5rem",
            margin: "0 auto",
          }}
        >
        {/* Logo + title */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            marginBottom: "0.5rem",
          }}
        >
          <img
            src={logoicon}
            alt="Visual AI Agent Builder Logo"
            style={{
              width: "40px",
              height: "40px",
              objectFit: "contain",
              borderRadius: "8px",
            }}
          />
          <span
            style={{
              background: "linear-gradient(90deg, #4f46e5 0%, #38bdf8 80%)",
              WebkitBackgroundClip: "text",
              color: "transparent",
              fontSize: "1.125rem",
              fontWeight: 700,
              letterSpacing: "0.01em",
            }}
          >
            Visual AI Agents Builder
          </span>
        </div>

        {/* User pill */}
        <div
          style={{
            alignItems: "center",
            backgroundColor: "#ffffff",
            border: "1px solid rgba(15, 23, 42, 0.08)",
            borderRadius: "1rem",
            boxShadow: "0 8px 28px rgba(15, 23, 42, 0.06)",
            display: "flex",
            gap: "0.75rem",
            padding: "0.875rem 1.25rem",
            width: "100%",
          }}
        >
          <div
            style={{
              width: "2.75rem",
              height: "2.75rem",
              borderRadius: "9999px",
              overflow: "hidden",
              border: "2px solid rgba(99, 102, 241, 0.35)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background:
                "linear-gradient(135deg, rgba(99,102,241,0.16), rgba(129,140,248,0.22))",
            }}
          >
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={displayName}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            ) : (
              <span
                style={{
                  color: "#312e81",
                  fontSize: "1.5rem",
                  fontWeight: 600,
                }}
              >
                {initials}
              </span>
            )}
          </div>

          <div
            style={{
              display: "flex",
              flex: 1,
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                fontSize: "1rem",
                fontWeight: 600,
                color: "#1e293b",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={displayName}
            >
              {displayName}
            </div>
            <div
              style={{
                color: "#475569",
                fontSize: "0.9rem",
                lineHeight: 1.3,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={emailAddress}
            >
              {emailAddress || "Signed in user"}
            </div>
          </div>
        </div>

        {/* Status / error */}
        {error && (
          <div
            style={{
              width: "100%",
              padding: "0.75rem 1rem",
              borderRadius: "0.75rem",
              backgroundColor: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#b91c1c",
              fontSize: "0.875rem",
            }}
          >
            <strong>Authentication error:</strong> {error}
          </div>
        )}

        {status && (
          <div
            style={{
              width: "100%",
              padding: "0.5rem 0.75rem",
              borderRadius: "999px",
              backgroundColor: "#eff6ff",
              color: "#1d4ed8",
              fontSize: "0.875rem",
              textAlign: "center",
            }}
          >
            {status}
          </div>
        )}

        {/* Org list / enterprise message */}
        <SignedIn>
          <OrganizationList
            hidePersonal
            afterCreateOrganizationUrl={`${LANDING_BASENAME}/organization?selected=true`}
            afterSelectOrganizationUrl={`${LANDING_BASENAME}/organization?selected=true`}
          />
        </SignedIn>

        <SignedOut>
          <div
            style={{
              width: "100%",
              padding: "0.75rem 1rem",
              borderRadius: "0.75rem",
              backgroundColor: "#eff6ff",
              border: "1px solid #bfdbfe",
              color: "#1d4ed8",
              fontSize: "0.875rem",
              textAlign: "center",
            }}
          >
            Your session expired. Please go back to the login page.
          </div>
        </SignedOut>
      </div>
    </div>
    </>
  );
}