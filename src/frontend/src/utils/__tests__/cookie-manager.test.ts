import { Cookies } from "react-cookie";

// Mock react-cookie
const mockCookiesInstance = {
  get: jest.fn(),
  set: jest.fn(),
  remove: jest.fn(),
};

jest.mock("react-cookie", () => ({
  Cookies: jest.fn().mockImplementation(() => mockCookiesInstance),
}));

// Import after mocking
import { cookieManager, getCookiesInstance } from "../cookie-manager";

describe("CookieManager", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Singleton Pattern", () => {
    it("should return the same instance across multiple calls", () => {
      const instance1 = getCookiesInstance();
      const instance2 = getCookiesInstance();

      expect(instance1).toBe(instance2);
      expect(instance1).toBe(mockCookiesInstance);
    });

    it("should only create one Cookies instance", () => {
      // Clear previous calls
      (Cookies as jest.Mock).mockClear();

      // Import fresh to test singleton
      const {
        getCookiesInstance: getNewInstance,
      } = require("../cookie-manager");

      getNewInstance();
      getNewInstance();
      getNewInstance();

      // Should only construct once due to singleton
      expect(Cookies).toHaveBeenCalledTimes(0); // Already constructed
    });

    it("should maintain the same instance across different imports", () => {
      const instance1 = getCookiesInstance();

      // Simulate a different module importing
      const { getCookiesInstance: importedGetter } =
        require("../cookie-manager");
      const instance2 = importedGetter();

      expect(instance1).toBe(instance2);
    });
  });

  describe("get method", () => {
    it("should retrieve a cookie value", () => {
      const cookieName = "test_cookie";
      const cookieValue = "test_value";

      mockCookiesInstance.get.mockReturnValue(cookieValue);

      const result = cookieManager.get(cookieName);

      expect(mockCookiesInstance.get).toHaveBeenCalledWith(cookieName);
      expect(result).toBe(cookieValue);
    });

    it("should return undefined for non-existent cookie", () => {
      mockCookiesInstance.get.mockReturnValue(undefined);

      const result = cookieManager.get("non_existent_cookie");

      expect(result).toBeUndefined();
    });

    it("should handle empty string cookie values", () => {
      mockCookiesInstance.get.mockReturnValue("");

      const result = cookieManager.get("empty_cookie");

      expect(result).toBe("");
    });

    it("should retrieve auth tokens correctly", () => {
      const accessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";
      mockCookiesInstance.get.mockReturnValue(accessToken);

      const result = cookieManager.get("access_token_lf");

      expect(mockCookiesInstance.get).toHaveBeenCalledWith("access_token_lf");
      expect(result).toBe(accessToken);
    });
  });

  describe("set method", () => {
    it("should set a cookie with appropriate security settings", () => {
      // Test environment uses HTTP by default
      const name = "test_cookie";
      const value = "test_value";

      cookieManager.set(name, value);

      // Verify cookie was set with security options
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(name, value, {
        path: "/",
        secure: expect.any(Boolean),
        sameSite: expect.stringMatching(/^(strict|lax|none)$/),
      });
    });

    it("should set a cookie without secure flag for HTTP", () => {
      // Default test environment is HTTP
      const name = "test_cookie";
      const value = "test_value";

      cookieManager.set(name, value);

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(name, value, {
        path: "/",
        secure: false,
        sameSite: "lax",
      });
    });

    it("should set a cookie with custom options", () => {
      const name = "custom_cookie";
      const value = "custom_value";
      const customOptions = {
        path: "/custom",
        secure: false,
        sameSite: "lax" as const,
        expires: new Date("2025-12-31"),
        domain: "example.com",
      };

      cookieManager.set(name, value, customOptions);

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(name, value, {
        path: "/custom",
        secure: false,
        sameSite: "lax",
        expires: customOptions.expires,
        domain: "example.com",
      });
    });

    it("should override default options with custom ones", () => {
      const name = "test_cookie";
      const value = "test_value";

      cookieManager.set(name, value, { secure: false, sameSite: "none" });

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(name, value, {
        path: "/",
        secure: false,
        sameSite: "none",
      });
    });

    it("should handle special characters in cookie values", () => {
      // Default test environment is HTTP
      const name = "special_cookie";
      const value = "value-with-special_chars@#$%";

      cookieManager.set(name, value);

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(name, value, {
        path: "/",
        secure: false,
        sameSite: "lax",
      });
    });

    it("should set auth tokens with security settings", () => {
      // Test environment behavior
      const accessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";

      cookieManager.set("access_token_lf", accessToken);

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "access_token_lf",
        accessToken,
        expect.objectContaining({
          path: "/",
          secure: expect.any(Boolean),
          sameSite: expect.stringMatching(/^(strict|lax|none)$/),
        }),
      );
    });

    it("should set auth tokens without secure flag for HTTP", () => {
      // Default test environment is HTTP
      const accessToken = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";

      cookieManager.set("access_token_lf", accessToken);

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "access_token_lf",
        accessToken,
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
    });

    it("should handle empty string values", () => {
      // Default test environment is HTTP
      cookieManager.set("empty_cookie", "");

      expect(mockCookiesInstance.set).toHaveBeenCalledWith("empty_cookie", "", {
        path: "/",
        secure: false,
        sameSite: "lax",
      });
    });
  });

  describe("remove method", () => {
    it("should remove a cookie with appropriate security settings", () => {
      // Test environment behavior
      const cookieName = "cookie_to_remove";

      cookieManager.remove(cookieName);

      expect(mockCookiesInstance.remove).toHaveBeenCalledWith(cookieName, {
        path: "/",
        secure: expect.any(Boolean),
        sameSite: expect.stringMatching(/^(strict|lax|none)$/),
      });
    });

    it("should remove a cookie with security settings for HTTP", () => {
      // Default test environment is HTTP
      const cookieName = "cookie_to_remove";

      cookieManager.remove(cookieName);

      expect(mockCookiesInstance.remove).toHaveBeenCalledWith(cookieName, {
        path: "/",
        secure: false,
        sameSite: "lax",
      });
    });

    it("should remove a cookie with custom path", () => {
      const cookieName = "cookie_to_remove";
      const customPath = "/custom";

      cookieManager.remove(cookieName, { path: customPath });

      expect(mockCookiesInstance.remove).toHaveBeenCalledWith(cookieName, {
        path: customPath,
        secure: false,
        sameSite: "lax",
      });
    });

    it("should remove auth tokens", () => {
      cookieManager.remove("access_token_lf");
      cookieManager.remove("refresh_token_lf");

      expect(mockCookiesInstance.remove).toHaveBeenCalledWith(
        "access_token_lf",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
      expect(mockCookiesInstance.remove).toHaveBeenCalledWith(
        "refresh_token_lf",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
    });
  });

  describe("clearAuthCookies method", () => {
    it("should clear all auth-related cookies", () => {
      cookieManager.clearAuthCookies();

      expect(mockCookiesInstance.remove).toHaveBeenCalledTimes(4);
      expect(mockCookiesInstance.remove).toHaveBeenCalledWith(
        "access_token_lf",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
      expect(mockCookiesInstance.remove).toHaveBeenCalledWith(
        "apikey_tkn_lflw",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
      expect(mockCookiesInstance.remove).toHaveBeenCalledWith(
        "refresh_token_lf",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
      expect(mockCookiesInstance.remove).toHaveBeenCalledWith("auto_login_lf", {
        path: "/",
        secure: false,
        sameSite: "lax",
      });
    });
  });

  describe("getCookies method", () => {
    it("should return the underlying Cookies instance", () => {
      const cookies = cookieManager.getCookies();

      expect(cookies).toBe(mockCookiesInstance);
      expect(cookies.get).toBeDefined();
      expect(cookies.set).toBeDefined();
      expect(cookies.remove).toBeDefined();
    });
  });

  describe("Integration scenarios", () => {
    it("should handle complete authentication flow", () => {
      const accessToken = "access_token_123";
      const refreshToken = "refresh_token_456";

      // Set tokens
      cookieManager.set("access_token_lf", accessToken);
      cookieManager.set("refresh_token_lf", refreshToken);

      expect(mockCookiesInstance.set).toHaveBeenCalledTimes(2);

      // Get tokens
      mockCookiesInstance.get.mockReturnValueOnce(accessToken);
      mockCookiesInstance.get.mockReturnValueOnce(refreshToken);

      const retrievedAccessToken = cookieManager.get("access_token_lf");
      const retrievedRefreshToken = cookieManager.get("refresh_token_lf");

      expect(retrievedAccessToken).toBe(accessToken);
      expect(retrievedRefreshToken).toBe(refreshToken);

      // Remove tokens on logout
      cookieManager.remove("access_token_lf");
      cookieManager.remove("refresh_token_lf");

      expect(mockCookiesInstance.remove).toHaveBeenCalledTimes(2);
    });

    it("should handle rapid successive operations", () => {
      // Simulate rapid cookie operations
      cookieManager.set("token1", "value1");
      cookieManager.set("token2", "value2");
      cookieManager.set("token3", "value3");

      mockCookiesInstance.get.mockReturnValue("value2");
      const value = cookieManager.get("token2");

      cookieManager.remove("token1");
      cookieManager.remove("token2");
      cookieManager.remove("token3");

      expect(mockCookiesInstance.set).toHaveBeenCalledTimes(3);
      expect(mockCookiesInstance.get).toHaveBeenCalledTimes(1);
      expect(mockCookiesInstance.remove).toHaveBeenCalledTimes(3);
      expect(value).toBe("value2");
    });

    it("should maintain consistency across multiple cookie operations", () => {
      // Set multiple cookies
      cookieManager.set("cookie1", "value1");
      cookieManager.set("cookie2", "value2");

      // Update existing cookie
      cookieManager.set("cookie1", "updated_value1");

      // Remove one cookie
      cookieManager.remove("cookie2");

      // Get remaining cookie
      mockCookiesInstance.get.mockReturnValue("updated_value1");
      const result = cookieManager.get("cookie1");

      expect(result).toBe("updated_value1");
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "cookie1",
        "value1",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "cookie1",
        "updated_value1",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
    });
  });

  describe("Edge cases", () => {
    it("should handle null and undefined gracefully", () => {
      mockCookiesInstance.get.mockReturnValue(null);
      expect(cookieManager.get("null_cookie")).toBeNull();

      mockCookiesInstance.get.mockReturnValue(undefined);
      expect(cookieManager.get("undefined_cookie")).toBeUndefined();
    });

    it("should handle long cookie values", () => {
      const longValue = "a".repeat(4000);
      cookieManager.set("long_cookie", longValue);

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "long_cookie",
        longValue,
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
    });

    it("should handle cookie names with special characters", () => {
      const specialName = "cookie_name-with.special@chars";
      cookieManager.set(specialName, "value");

      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        specialName,
        "value",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );
    });
  });

  describe("Fix for race condition (issue #10348)", () => {
    it("should ensure all cookie operations use the same instance", () => {
      // Simulate multiple components accessing cookies simultaneously
      const instance1 = getCookiesInstance();
      const instance2 = cookieManager.getCookies();
      const instance3 = getCookiesInstance();

      // All should be the same instance
      expect(instance1).toBe(instance2);
      expect(instance2).toBe(instance3);
      expect(instance1).toBe(mockCookiesInstance);
    });

    it("should prevent desynchronization when setting and getting cookies quickly", () => {
      // Set a cookie
      cookieManager.set("access_token_lf", "token_123");

      // Verify set was called
      expect(mockCookiesInstance.set).toHaveBeenCalledWith(
        "access_token_lf",
        "token_123",
        {
          path: "/",
          secure: false,
          sameSite: "lax",
        },
      );

      // Immediately get it using the same manager
      mockCookiesInstance.get.mockReturnValue("token_123");
      const result = cookieManager.get("access_token_lf");

      // Should work because they use the same instance
      expect(result).toBe("token_123");
      expect(mockCookiesInstance.get).toHaveBeenCalledWith("access_token_lf");
    });
  });
});
