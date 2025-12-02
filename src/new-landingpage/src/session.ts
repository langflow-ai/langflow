export const LANGFLOW_ACCESS_TOKEN = "access_token_lf";
export const LANGFLOW_REFRESH_TOKEN = "refresh_token_lf";
export const ACTIVE_ORG_STORAGE_KEY = "lf-active-org";
export const ORG_SELECTED_KEY = "isOrgSelected";

export function hasWorkspaceSession(cookies: Record<string, any>) {
  const token = cookies[LANGFLOW_ACCESS_TOKEN];
  const orgSelected = localStorage.getItem(ORG_SELECTED_KEY) === "true";
  const orgId = localStorage.getItem(ACTIVE_ORG_STORAGE_KEY);

  return Boolean(token && orgSelected && orgId);
}

export function clearStoredOrgSelection() {
  if (typeof window === "undefined") return;

  try {
    localStorage.removeItem(ORG_SELECTED_KEY);
    localStorage.removeItem(ACTIVE_ORG_STORAGE_KEY);
  } catch (error) {
    console.warn("[session] Unable to clear organization selection", error);
  }
}