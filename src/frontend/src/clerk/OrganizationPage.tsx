import { useLogout } from "@/clerk/auth";
import { AuthContext } from "@/contexts/authContext";
import { LoadingPage } from "@/pages/LoadingPage";
import authStore from "@/stores/authStore";
import {
  OrganizationList,
  useAuth,
  useOrganization,
  useUser,
} from "@clerk/clerk-react";
import { useContext, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  backendLogin,
  createOrganisation,
  ensureLangflowUser,
  setStoredActiveOrgId,
} from "./auth";
import logoicon from "../assets/visualailogo.png"

export default function OrganizationSwitcherPage() {
  const { getToken } = useAuth();
  const { organization } = useOrganization();
  const { user } = useUser();
  const navigate = useNavigate();
  const location = useLocation();
  const { mutateAsync: logout } = useLogout();
  const bootstrapped = useRef(false);
  const { login } = useContext(AuthContext);
  const justLoggedIn = useRef(false);
  const searchParams = new URLSearchParams(location.search);
  const isOrgSelectedManually = searchParams.get("selected") === "true";
  const [isBootstrapping, setIsBootstrapping] = useState(false);

  type EnterpriseDetectionUser = {
    enterpriseAccounts?: unknown[] | null;
    samlAccounts?: unknown[] | null;
    externalAccounts?:
      | Array<{
          provider?: string | null;
          strategy?: string | null;
          verification?: { strategy?: string | null } | null;
        }>
      | null;
  };
  const enterpriseDetectionUser = user as unknown as EnterpriseDetectionUser | null;
  const enterpriseAccounts = enterpriseDetectionUser?.enterpriseAccounts ?? [];
  const samlAccounts = enterpriseDetectionUser?.samlAccounts ?? [];
  const externalAccounts = enterpriseDetectionUser?.externalAccounts ?? [];
  const hasEnterpriseAccounts =
    (Array.isArray(enterpriseAccounts) && enterpriseAccounts.length > 0) ||
    (Array.isArray(samlAccounts) && samlAccounts.length > 0) ||
    (Array.isArray(externalAccounts) &&
      externalAccounts.some((account) => {
        if (!account) return false;
        const provider = account.provider?.toLowerCase() ?? "";
        const strategy = account.strategy?.toLowerCase() ?? "";
        const verificationStrategy = account.verification?.strategy?.toLowerCase() ?? "";
        return (
          strategy === "enterprise_sso" ||
          strategy === "saml" ||
          verificationStrategy === "enterprise_sso" ||
          verificationStrategy === "saml" ||
          provider === "saml" ||
          provider.startsWith("saml_")
        );
      }));
  const isEnterpriseUser = hasEnterpriseAccounts;
  const organizationMemberships = user?.organizationMemberships ?? [];
  const hasOrganizations = organizationMemberships.length > 0;
  const shouldShowEnterpriseEmptyState = isEnterpriseUser && !hasOrganizations;

  useEffect(() => {
    if (!organization?.id || !isOrgSelectedManually || bootstrapped.current)
      return;

    bootstrapped.current = true;
    setIsBootstrapping(true);
    const activeOrgId = organization.id;

    (async () => {
      console.log("[OrgSwitcherPage] Starting bootstrap flow...");

      const orgToken = await getToken();
      if (!orgToken) throw new Error("Missing Clerk org token");

      const username =
        user?.username ||
        user?.primaryEmailAddress?.emailAddress ||
        user?.id ||
        "clerk_user";
      const email = user?.primaryEmailAddress?.emailAddress;
      try {
        // Step 1: Create backend organization (DB provisioning or linking)
        console.debug("[OrgSwitcherPage] Calling createOrganisation()");
        await createOrganisation(orgToken);
        console.debug("[OrgSwitcherPage] createOrganisation() completed");

        // Step 2: Ensure Langflow user exists via /whoami or /users
        console.debug("[OrgSwitcherPage] Calling ensureLangflowUser()");
        await ensureLangflowUser(orgToken, username, email);
        // Step 3: Backend login using dummy password flow
        console.debug("[OrgSwitcherPage] Calling backendLogin()");
        const tokens = await backendLogin(username, orgToken);
        console.debug("[OrgSwitcherPage] backendLogin() succeeded");

        // Step 4: Save access & refresh tokens into store and cookies
        login(orgToken, "login", tokens.refresh_token);
        justLoggedIn.current = true;

        // Step 5: Only now mark org as selected
        authStore.getState().setIsOrgSelected(true);
        sessionStorage.setItem("isOrgSelected", "true");
        setStoredActiveOrgId(activeOrgId);
        console.debug("[OrgSwitcherPage] Org selection state marked");

        // Step 6: Navigate to /flows
        console.debug("[OrgSwitcherPage] Redirecting to /flows");
        navigate("/flows", { replace: true });
      } catch (err) {
        if (!justLoggedIn.current) {
          console.error("[OrgSwitcherPage] Error during bootstrap", err);
          await logout();
        } else {
          console.warn(
            "[OrgSwitcherPage] Ignoring error after successful login",
            err,
          );
        }
      } finally {
        setIsBootstrapping(false);
      }
    })().catch((err) => {
      console.error("[OrgSwitcherPage] Bootstrap failed", err);
      bootstrapped.current = false;
      setIsBootstrapping(false);
    });
  }, [
    organization?.id,
    isOrgSelectedManually,
    getToken,
    user,
    navigate,
    login,
    logout,
  ]);

  if (isOrgSelectedManually || isBootstrapping) {
    return <LoadingPage />;
  }

  const displayName =
    (user?.fullName && user.fullName.trim()) ||
    user?.username ||
    [user?.firstName, user?.lastName].filter(Boolean).join(" ") ||
    user?.primaryEmailAddress?.emailAddress ||
    user?.id ||
    "";

  const emailAddress =
    user?.primaryEmailAddress?.emailAddress ||
    user?.emailAddresses?.[0]?.emailAddress ||
    "";

  const avatarUrl = user?.imageUrl;
  const initials = (
    (user?.firstName?.[0] || "") + (user?.lastName?.[0] || user?.firstName?.[1] || "")
  ).toUpperCase();
   
 const isMobile = window.innerWidth < 640; 
  return (
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
                alt={displayName || "Current user"}
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
                {initials || (displayName?.[0]?.toUpperCase() ?? "U")}
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
              title={displayName || undefined}
            >
              {displayName || "Current member"}
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
              title={emailAddress || undefined}
            >
              {emailAddress || "Signed in user"}
            </div>
          </div>
        </div>

        {shouldShowEnterpriseEmptyState ? (
          <div
            style={{
              maxWidth: "32rem",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              gap: "0.75rem",
              margin: "0 auto",
            }}
          >
            <h1 style={{ fontSize: "1.5rem", fontWeight: 600 }}>
              You&apos;re signed in with enterprise SSO
            </h1>
            <p style={{ color: "#4b5563", lineHeight: 1.5 }}>
              Your account is managed by your organization, so creating new
              organizations is disabled. Please contact your administrator if
              you need a new organization to be set up for you.
            </p>
          </div>
        ) : (
          <div
            style={{
              width: "100%",
              background: "transparent",
              border: "none",
              boxShadow: "none",
              boxSizing: "border-box",
              padding: 0,
              margin: "0 auto",
              transform: isMobile ? "none" : "translateX(40px)",
            }}
          >
            <OrganizationList
              hidePersonal
              afterCreateOrganizationUrl="/organization?selected=true"
              afterSelectOrganizationUrl="/organization?selected=true"
              appearance={
                isEnterpriseUser
                  ? {
                      elements: {
                        organizationListCreateOrganizationActionButton: {
                          display: "none",
                        },
                      },
                    }
                  : undefined
              }
            />
          </div>
        )}
      </div>
    </div>
  );
}
