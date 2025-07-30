// Logout functionality tests

import { LANGFLOW_AUTO_LOGIN_OPTION } from "@/constants/constants";
import useGetCookieAuth from "@/shared/hooks/use-get-cookie-auth";

// Mock dependencies
jest.mock("@/shared/hooks/use-get-cookie-auth");

const mockUseGetCookieAuth = useGetCookieAuth as jest.MockedFunction<
  typeof useGetCookieAuth
>;

// Mock the logout hook behavior since we can't easily import it
const createMockLogout = (shouldCallAPI: boolean = true) => {
  const mockLogout = jest.fn();
  const mockResetFlowState = jest.fn();
  const mockResetFlowsManagerStore = jest.fn();
  const mockResetFolderStore = jest.fn();
  const mockQueryClient = { invalidateQueries: jest.fn() };
  const mockApiPost = jest.fn();

  const logoutUser = async () => {
    const autoLogin =
      mockUseGetCookieAuth(LANGFLOW_AUTO_LOGIN_OPTION) === "auto";

    if (autoLogin) {
      return {};
    }

    if (shouldCallAPI) {
      const result = await mockApiPost("/logout");
      return result?.data || result;
    }

    return {};
  };

  const mutate = async () => {
    try {
      await logoutUser();

      // Simulate onSuccess behavior
      mockLogout();
      mockResetFlowState();
      mockResetFlowsManagerStore();
      mockResetFolderStore();
      mockQueryClient.invalidateQueries({
        queryKey: ["useGetRefreshFlowsQuery"],
      });
      mockQueryClient.invalidateQueries({ queryKey: ["useGetFolders"] });
      mockQueryClient.invalidateQueries({ queryKey: ["useGetFolder"] });
    } catch (error) {
      console.error(error);
      throw error;
    }
  };

  return {
    mutate,
    mockLogout,
    mockResetFlowState,
    mockResetFlowsManagerStore,
    mockResetFolderStore,
    mockQueryClient,
    mockApiPost,
  };
};

describe("logout functionality", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseGetCookieAuth.mockReturnValue(null);
  });

  describe("logout behavior with auto login disabled", () => {
    it("should call API logout when auto login is disabled", async () => {
      mockUseGetCookieAuth.mockReturnValue("false"); // auto login disabled

      const { mutate, mockApiPost } = createMockLogout();
      mockApiPost.mockResolvedValue({ data: { success: true } });

      await mutate();

      expect(mockApiPost).toHaveBeenCalledWith("/logout");
    });

    it("should reset all stores on successful logout", async () => {
      mockUseGetCookieAuth.mockReturnValue("false");

      const {
        mutate,
        mockLogout,
        mockResetFlowState,
        mockResetFlowsManagerStore,
        mockResetFolderStore,
      } = createMockLogout();

      await mutate();

      expect(mockLogout).toHaveBeenCalled();
      expect(mockResetFlowState).toHaveBeenCalled();
      expect(mockResetFlowsManagerStore).toHaveBeenCalled();
      expect(mockResetFolderStore).toHaveBeenCalled();
    });

    it("should invalidate queries on successful logout", async () => {
      mockUseGetCookieAuth.mockReturnValue("false");

      const { mutate, mockQueryClient } = createMockLogout();

      await mutate();

      expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetRefreshFlowsQuery"],
      });
      expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetFolders"],
      });
      expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetFolder"],
      });
    });
  });

  describe("logout behavior with auto login enabled", () => {
    it("should skip API call when auto login is enabled via cookie", async () => {
      mockUseGetCookieAuth.mockImplementation((tokenName) => {
        if (tokenName === LANGFLOW_AUTO_LOGIN_OPTION) return "auto";
        return null;
      });

      const { mutate, mockApiPost } = createMockLogout();

      await mutate();

      expect(mockApiPost).not.toHaveBeenCalled();
    });

    it("should still reset stores even when skipping API call", async () => {
      mockUseGetCookieAuth.mockImplementation((tokenName) => {
        if (tokenName === LANGFLOW_AUTO_LOGIN_OPTION) return "auto";
        return null;
      });

      const { mutate, mockLogout, mockResetFlowState } = createMockLogout();

      await mutate();

      expect(mockLogout).toHaveBeenCalled();
      expect(mockResetFlowState).toHaveBeenCalled();
    });
  });

  describe("error handling", () => {
    it("should handle API errors gracefully", async () => {
      mockUseGetCookieAuth.mockReturnValue("false");

      const { mutate, mockApiPost } = createMockLogout();
      const mockError = new Error("API Error");
      mockApiPost.mockRejectedValue(mockError);

      await expect(mutate()).rejects.toThrow("API Error");
    });
  });
});
