import { renderHook } from "@testing-library/react";
import { usePlaygroundConfig } from "../use-playground-config";

const mockConfig = {
  frontend_timeout: 60,
  max_file_size_upload: 100,
  event_delivery: "polling",
  voice_mode_available: true,
};

const mockUseGetConfig = jest.fn();

jest.mock("@/controllers/API/queries/config/use-get-config", () => ({
  useGetConfig: (options: Record<string, unknown>) => mockUseGetConfig(options),
}));

describe("usePlaygroundConfig", () => {
  beforeEach(() => {
    mockUseGetConfig.mockClear();
  });

  it("should call useGetConfig", () => {
    mockUseGetConfig.mockReturnValue({ data: mockConfig });

    renderHook(() => usePlaygroundConfig());

    expect(mockUseGetConfig).toHaveBeenCalledWith({});
  });

  it("should return config data", () => {
    mockUseGetConfig.mockReturnValue({ data: mockConfig });

    const { result } = renderHook(() => usePlaygroundConfig());

    expect(result.current).toEqual(mockConfig);
  });

  it("should return undefined when config is not loaded yet", () => {
    mockUseGetConfig.mockReturnValue({ data: undefined });

    const { result } = renderHook(() => usePlaygroundConfig());

    expect(result.current).toBeUndefined();
  });
});
