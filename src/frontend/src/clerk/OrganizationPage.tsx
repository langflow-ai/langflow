import { OrganizationList, useAuth, useOrganization, useUser } from "@clerk/clerk-react";
import { useContext, useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ensureLangflowUser, createOrganisation, backendLogin } from "./auth";
import authStore from "@/stores/authStore";
import { useLogout } from "@/clerk/auth";
import { AuthContext } from "@/contexts/authContext";

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

useEffect(() => {
  if (!organization?.id || !isOrgSelectedManually || bootstrapped.current) return;

    bootstrapped.current = true;

    (async () => {
      console.log("[OrgSwitcherPage] Starting bootstrap flow...");

      const orgToken = await getToken();
      if (!orgToken) throw new Error("Missing Clerk org token");

      const username =
        user?.username ||
        user?.primaryEmailAddress?.emailAddress ||
        user?.id ||
        "clerk_user";
      try{
        // Step 1: Create backend organization (DB provisioning or linking)
        console.debug("[OrgSwitcherPage] Calling createOrganisation()");
        await createOrganisation(orgToken);
        console.debug("[OrgSwitcherPage] createOrganisation() completed");
  
        // Step 2: Ensure Langflow user exists via /whoami or /users
        console.debug("[OrgSwitcherPage] Calling ensureLangflowUser()");
        await ensureLangflowUser(orgToken, username);
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
        console.debug("[OrgSwitcherPage] Org selection state marked");
  
        // Step 6: Navigate to /flows
        console.debug("[OrgSwitcherPage] Redirecting to /flows");
        navigate("/flows", { replace: true });
      }catch(err){
        if(!justLoggedIn.current){
          console.error("[OrgSwitcherPage] Error during bootstrap", err);
          await logout();
        }else{
          console.warn("[OrgSwitcherPage] Ignoring error after successful login", err);
        }
      }
    })().catch((err) => {
      console.error("[OrgSwitcherPage] Bootstrap failed", err);
      bootstrapped.current = false;
    });
  }, [organization?.id, isOrgSelectedManually, getToken, user, navigate]);

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
      }}
    >
      <OrganizationList
        hidePersonal
        afterCreateOrganizationUrl="/organization?selected=true"
        afterSelectOrganizationUrl="/organization?selected=true"
      />
    </div>
  );
}
