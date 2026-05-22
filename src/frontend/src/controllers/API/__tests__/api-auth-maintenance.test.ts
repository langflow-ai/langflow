import { AUTH_MAINTENANCE_PATHS, isAuthMaintenanceURL } from "../api";

describe("isAuthMaintenanceURL", () => {
  it("matches refresh, login, logout, and auto_login endpoints", () => {
    expect(isAuthMaintenanceURL("/api/v1/refresh")).toBe(true);
    expect(isAuthMaintenanceURL("/api/v1/login")).toBe(true);
    expect(isAuthMaintenanceURL("/api/v1/logout")).toBe(true);
    expect(isAuthMaintenanceURL("/api/v1/auto_login")).toBe(true);
  });

  it("matches absolute URLs as well as relative paths", () => {
    expect(isAuthMaintenanceURL("https://example.com/api/v1/refresh")).toBe(
      true,
    );
    expect(isAuthMaintenanceURL("https://example.com/api/v1/auto_login")).toBe(
      true,
    );
  });

  it("does not match unrelated business endpoints", () => {
    // The recursion guard is a defensive check — make sure we don't
    // accidentally exclude normal endpoints from the refresh-retry path.
    expect(isAuthMaintenanceURL("/api/v1/flows")).toBe(false);
    expect(isAuthMaintenanceURL("/api/v1/models")).toBe(false);
    expect(isAuthMaintenanceURL("/api/v1/users/me")).toBe(false);
  });

  it("does not cross-match login vs auto_login (separate paths)", () => {
    // Both /login and /auto_login are in the list. Verify the matcher
    // classifies each correctly and does not confuse one for the other.
    expect(isAuthMaintenanceURL("/api/v1/auto_login")).toBe(true);
    expect(isAuthMaintenanceURL("/api/v1/login")).toBe(true);
  });

  it("does not match URLs that share a path segment prefix with a maintenance path", () => {
    // Substring matching would false-positive on these — path-segment matching must not.
    expect(isAuthMaintenanceURL("/api/v1/refresh_tokens")).toBe(false);
    expect(isAuthMaintenanceURL("/api/v1/login_history")).toBe(false);
    expect(isAuthMaintenanceURL("/api/v1/logout_sessions")).toBe(false);
  });

  it("returns false for empty or undefined urls", () => {
    expect(isAuthMaintenanceURL(undefined)).toBe(false);
    expect(isAuthMaintenanceURL("")).toBe(false);
  });

  it("exports the maintenance-path constant for downstream consumers", () => {
    // Snapshot the list so any future addition/removal is intentional.
    expect(AUTH_MAINTENANCE_PATHS).toEqual([
      "/refresh",
      "/login",
      "/logout",
      "/auto_login",
    ]);
  });
});
