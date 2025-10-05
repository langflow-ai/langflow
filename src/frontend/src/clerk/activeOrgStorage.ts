export const ACTIVE_ORG_STORAGE_KEY = "lf-active-org";

export function getStoredActiveOrgId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return localStorage.getItem(ACTIVE_ORG_STORAGE_KEY);
  } catch (error) {
    console.warn("[activeOrgStorage] Unable to read active org from storage", error);
    return null;
  }
}

export function setStoredActiveOrgId(orgId: string | null) {
  if (typeof window === "undefined") {
    return;
  }

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

export function clearStoredActiveOrgId() {
  setStoredActiveOrgId(null);
}
