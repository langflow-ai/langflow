// Refresh token functionality tests

// Mock all dependencies before imports
const mockCookieManagerSet = jest.fn();

jest.mock("@/utils/cookie-manager", () => ({
  cookieManager: {
    set: mockCookieManagerSet,
    get: jest.fn(),
    remove: jest.fn(),
    getCookies: jest.fn(),
    clearAuthCookies: jest.fn(),
  },
  getCookiesInstance: jest.fn(() => ({
    get: jest.fn(),
    set: jest.fn(),
    remove: jest.fn(),
  })),
}));

jest.mock(
  "@/stores/authStore",
  () => jest.fn((selector) => false), // autoLogin = false
);

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: jest.fn(),
  },
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn((key, fn, options) => ({
      mutate: async () => {
        return await fn();
      },
    })),
  })),
}));

import { useRefreshAccessToken } from "../use-post-refresh-access";

const mockApiPost = require("@/controllers/API/api").api.post;

describe("refresh token functionality", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("successful token refresh", () => {
    it("should call refresh API and set new refresh token cookie", async () => {
      const mockRefreshResponse = {
        access_token: "new-access-token",
        refresh_token: "new-refresh-token",
        token_type: "bearer",
      };

      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      const refreshMutation = useRefreshAccessToken();
      const result = await refreshMutation.mutate();

      expect(mockApiPost).toHaveBeenCalledWith(
        expect.stringContaining("refresh"),
      );
      expect(mockCookieManagerSet).toHaveBeenCalledWith(
        "refresh_token_lf",
        "new-refresh-token",
      );
      expect(result).toEqual(mockRefreshResponse);
    });

    it("should return the refresh response data", async () => {
      const mockRefreshResponse = {
        access_token: "new-access-token-123",
        refresh_token: "new-refresh-token-456",
        token_type: "bearer",
      };

      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      const refreshMutation = useRefreshAccessToken();
      const result = await refreshMutation.mutate();

      expect(result).toEqual(mockRefreshResponse);
    });
  });

  describe("error handling", () => {
    it("should throw error when refresh API fails", async () => {
      const mockError = new Error("Refresh failed");
      mockApiPost.mockRejectedValue(mockError);

      const refreshMutation = useRefreshAccessToken();
      await expect(refreshMutation.mutate()).rejects.toThrow("Refresh failed");
    });

    it("should not set cookie when API fails", async () => {
      const mockError = new Error("API Error");
      mockApiPost.mockRejectedValue(mockError);

      const refreshMutation = useRefreshAccessToken();

      try {
        await refreshMutation.mutate();
      } catch (_error) {
        // Expected to throw
      }

      expect(mockCookieManagerSet).not.toHaveBeenCalled();
    });
  });

  describe("cookie management", () => {
    it("should use cookieManager for setting refresh token", async () => {
      const mockRefreshResponse = {
        access_token: "access-token",
        refresh_token: "refresh-token-xyz",
        token_type: "bearer",
      };

      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      const refreshMutation = useRefreshAccessToken();
      await refreshMutation.mutate();

      expect(mockCookieManagerSet).toHaveBeenCalledTimes(1);
      expect(mockCookieManagerSet).toHaveBeenCalledWith(
        "refresh_token_lf",
        "refresh-token-xyz",
      );
    });

    it("should set refresh token cookie before returning response", async () => {
      const mockRefreshResponse = {
        access_token: "access-token",
        refresh_token: "refresh-token-abc",
        token_type: "bearer",
      };

      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      const refreshMutation = useRefreshAccessToken();
      const response = await refreshMutation.mutate();

      // Verify cookie was set before response was returned
      expect(mockCookieManagerSet).toHaveBeenCalledWith(
        "refresh_token_lf",
        "refresh-token-abc",
      );
      expect(response).toEqual(mockRefreshResponse);
    });
  });
});
