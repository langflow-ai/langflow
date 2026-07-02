/**
 * Regression tests for issue #13766:
 * "Login screen not displayed (stuck on loading, repeated auto_login/refresh loop)"
 *
 * Root cause: when LANGFLOW_AUTO_LOGIN=false the backend returns HTTP 403 with:
 *   { "detail": { "message": "Auto login is disabled.", "auto_login": false } }
 *
 * The previous code read `error.response?.data?.auto_login`, which is `undefined`
 * because FastAPI nests the payload under `detail`. As a result
 * `autoLoginDisabledByBackend` was always `false`, causing an infinite retry loop
 * and the login screen never being rendered.
 */

import {
  type AutoLoginErrorResponse,
  isAutoLoginDisabled,
} from "../use-get-autologin";

describe("isAutoLoginDisabled (issue #13766)", () => {
  describe("FastAPI nested shape — { detail: { auto_login: false } }", () => {
    it("returns true when auto_login is nested under detail", () => {
      const data: AutoLoginErrorResponse = {
        detail: { auto_login: false, message: "Auto login is disabled." },
      };
      expect(isAutoLoginDisabled(data)).toBe(true);
    });

    it("returns false when detail.auto_login is true", () => {
      const data: AutoLoginErrorResponse = {
        detail: { auto_login: true },
      };
      expect(isAutoLoginDisabled(data)).toBe(false);
    });

    it("returns false when detail exists but auto_login is absent", () => {
      const data: AutoLoginErrorResponse = {
        detail: { message: "some other error" },
      };
      expect(isAutoLoginDisabled(data)).toBe(false);
    });
  });

  describe("Previous buggy read — data.auto_login (undefined for FastAPI errors)", () => {
    it("data.auto_login is undefined when only detail is present, but isAutoLoginDisabled still returns true", () => {
      const data = {
        detail: { auto_login: false },
      } as AutoLoginErrorResponse;
      // The old code read data.auto_login directly — undefined, so it missed the signal
      expect(data.auto_login).toBeUndefined();
      // The fixed function reads data.detail.auto_login and correctly returns true
      expect(isAutoLoginDisabled(data)).toBe(true);
    });
  });

  describe("Flat shape — { auto_login: false } — forward-compatibility fallback", () => {
    it("returns true when auto_login is at the top level", () => {
      const data: AutoLoginErrorResponse = { auto_login: false };
      expect(isAutoLoginDisabled(data)).toBe(true);
    });
  });

  describe("Edge cases", () => {
    it("returns false when data is undefined", () => {
      expect(isAutoLoginDisabled(undefined)).toBe(false);
    });

    it("returns false when data is an empty object", () => {
      expect(isAutoLoginDisabled({})).toBe(false);
    });
  });
});
