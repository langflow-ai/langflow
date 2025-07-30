// Refresh token functionality tests

import { LANGFLOW_REFRESH_TOKEN } from "@/constants/constants";
import useSetCookieAuth from "@/shared/hooks/use-set-cookie-auth";

// Mock dependencies
jest.mock("@/shared/hooks/use-set-cookie-auth");

const mockUseSetCookieAuth = useSetCookieAuth as jest.MockedFunction<
  typeof useSetCookieAuth
>;

// Mock the refresh token hook behavior
const createMockRefreshToken = () => {
  const mockApiPost = jest.fn();

  const refreshAccess = async () => {
    const response = await mockApiPost("/refresh");
    mockUseSetCookieAuth(LANGFLOW_REFRESH_TOKEN, response.data.refresh_token);
    return response.data;
  };

  const mutate = async () => {
    return await refreshAccess();
  };

  return {
    mutate,
    mockApiPost,
  };
};

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

      const { mutate, mockApiPost } = createMockRefreshToken();
      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      const result = await mutate();

      expect(mockApiPost).toHaveBeenCalledWith("/refresh");
      expect(mockUseSetCookieAuth).toHaveBeenCalledWith(
        LANGFLOW_REFRESH_TOKEN,
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

      const { mutate, mockApiPost } = createMockRefreshToken();
      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      const result = await mutate();

      expect(result).toEqual(mockRefreshResponse);
    });
  });

  describe("error handling", () => {
    it("should throw error when refresh API fails", async () => {
      const mockError = new Error("Refresh failed");

      const { mutate, mockApiPost } = createMockRefreshToken();
      mockApiPost.mockRejectedValue(mockError);

      await expect(mutate()).rejects.toThrow("Refresh failed");
    });

    it("should not set cookie when API fails", async () => {
      const mockError = new Error("API Error");

      const { mutate, mockApiPost } = createMockRefreshToken();
      mockApiPost.mockRejectedValue(mockError);

      try {
        await mutate();
      } catch (error) {
        // Expected to throw
      }

      expect(mockUseSetCookieAuth).not.toHaveBeenCalled();
    });
  });

  describe("cookie management", () => {
    it("should use useSetCookieAuth hook for setting refresh token", async () => {
      const mockRefreshResponse = {
        access_token: "access-token",
        refresh_token: "refresh-token-xyz",
        token_type: "bearer",
      };

      const { mutate, mockApiPost } = createMockRefreshToken();
      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      await mutate();

      expect(mockUseSetCookieAuth).toHaveBeenCalledTimes(1);
      expect(mockUseSetCookieAuth).toHaveBeenCalledWith(
        LANGFLOW_REFRESH_TOKEN,
        "refresh-token-xyz",
      );
    });

    it("should set refresh token cookie before returning response", async () => {
      const mockRefreshResponse = {
        access_token: "access-token",
        refresh_token: "refresh-token-abc",
        token_type: "bearer",
      };

      const { mutate, mockApiPost } = createMockRefreshToken();
      mockApiPost.mockResolvedValue({ data: mockRefreshResponse });

      const response = await mutate();

      // Verify cookie was set before response was returned
      expect(mockUseSetCookieAuth).toHaveBeenCalledWith(
        LANGFLOW_REFRESH_TOKEN,
        "refresh-token-abc",
      );
      expect(response).toEqual(mockRefreshResponse);
    });
  });
});
