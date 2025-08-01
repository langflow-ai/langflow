// Refresh token functionality tests

// Mock all dependencies before imports
jest.mock("@/utils/utils", () => ({
  setAuthCookie: jest.fn(),
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

jest.mock("react-cookie", () => ({
  Cookies: jest.fn().mockImplementation(() => ({})),
}));

import { useRefreshAccessToken } from "../use-post-refresh-access";

const mockSetAuthCookie = require("@/utils/utils").setAuthCookie;
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
      expect(mockSetAuthCookie).toHaveBeenCalledWith(
        expect.any(Object), // cookies instance
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
      } catch (error) {
        // Expected to throw
      }

      expect(mockSetAuthCookie).not.toHaveBeenCalled();
    });
  });

  describe("cookie management", () => {
    it("should use useSetCookieAuth hook for setting refresh token", async () => {
      const mockRefreshResponse = {
        access_token: "access-token",
        refresh_token: "refresh-token-xyz",
        token_type: "bearer",
      };

      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      const refreshMutation = useRefreshAccessToken();
      await refreshMutation.mutate();

      expect(mockSetAuthCookie).toHaveBeenCalledTimes(1);
      expect(mockSetAuthCookie).toHaveBeenCalledWith(
        expect.any(Object), // cookies instance
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
      expect(mockSetAuthCookie).toHaveBeenCalledWith(
        expect.any(Object), // cookies instance
        "refresh_token_lf",
        "refresh-token-abc",
      );
      expect(response).toEqual(mockRefreshResponse);
    });
  });
});
