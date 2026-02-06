import { renderHook } from "@testing-library/react";
import { usePlaygroundConfig } from "../use-playground-config";

const mockAuthConfig = {
  frontend_timeout: 60,
  auto_saving: true,
  auto_saving_interval: 1000,
  health_check_max_retries: 3,
  max_file_size_upload: 100,
  feature_flags: {},
  webhook_polling_interval: 5000,
  serialization_max_items_length: 100,
  event_delivery: "polling",
  webhook_auth_enable: true,
  voice_mode_available: true,
  default_folder_name: "My Projects",
  hide_getting_started_progress: false,
};

const mockPublicConfig = {
  frontend_timeout: 60,
  max_file_size_upload: 100,
  event_delivery: "polling",
  voice_mode_available: false,
};

const mockUseGetConfig = jest.fn();
const mockUseGetPublicConfig = jest.fn();

jest.mock("@/controllers/API/queries/config/use-get-config", () => ({
  useGetConfig: (options: { enabled: boolean }) => mockUseGetConfig(options),
}));

jest.mock("@/controllers/API/queries/config/use-get-public-config", () => ({
  useGetPublicConfig: (options: { enabled: boolean }) =>
    mockUseGetPublicConfig(options),
}));

describe("usePlaygroundConfig", () => {
  beforeEach(() => {
    mockUseGetConfig.mockClear();
    mockUseGetPublicConfig.mockClear();
  });

  describe("when playgroundPage is false (authenticated mode)", () => {
    beforeEach(() => {
      mockUseGetConfig.mockReturnValue({ data: mockAuthConfig });
      mockUseGetPublicConfig.mockReturnValue({ data: undefined });
    });

    it("should call useGetConfig with enabled: true", () => {
      renderHook(() => usePlaygroundConfig(false));

      expect(mockUseGetConfig).toHaveBeenCalledWith({ enabled: true });
    });

    it("should call useGetPublicConfig with enabled: false", () => {
      renderHook(() => usePlaygroundConfig(false));

      expect(mockUseGetPublicConfig).toHaveBeenCalledWith({ enabled: false });
    });

    it("should return authConfig data", () => {
      const { result } = renderHook(() => usePlaygroundConfig(false));

      expect(result.current).toEqual(mockAuthConfig);
    });
  });

  describe("when playgroundPage is true (unauthenticated mode)", () => {
    beforeEach(() => {
      mockUseGetConfig.mockReturnValue({ data: undefined });
      mockUseGetPublicConfig.mockReturnValue({ data: mockPublicConfig });
    });

    it("should call useGetConfig with enabled: false", () => {
      renderHook(() => usePlaygroundConfig(true));

      expect(mockUseGetConfig).toHaveBeenCalledWith({ enabled: false });
    });

    it("should call useGetPublicConfig with enabled: true", () => {
      renderHook(() => usePlaygroundConfig(true));

      expect(mockUseGetPublicConfig).toHaveBeenCalledWith({ enabled: true });
    });

    it("should return publicConfig data", () => {
      const { result } = renderHook(() => usePlaygroundConfig(true));

      expect(result.current).toEqual(mockPublicConfig);
    });
  });

  describe("edge cases", () => {
    it("should return undefined when authConfig is not loaded yet", () => {
      mockUseGetConfig.mockReturnValue({ data: undefined });
      mockUseGetPublicConfig.mockReturnValue({ data: undefined });

      const { result } = renderHook(() => usePlaygroundConfig(false));

      expect(result.current).toBeUndefined();
    });

    it("should return undefined when publicConfig is not loaded yet", () => {
      mockUseGetConfig.mockReturnValue({ data: undefined });
      mockUseGetPublicConfig.mockReturnValue({ data: undefined });

      const { result } = renderHook(() => usePlaygroundConfig(true));

      expect(result.current).toBeUndefined();
    });
  });
});
