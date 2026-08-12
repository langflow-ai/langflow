import { act, renderHook } from "@testing-library/react";
import { EventDeliveryType } from "@/constants/enums";
import { useUtilityStore } from "@/stores/utilityStore";

const mockApiGet = jest.fn();
let mockQueryFn: (() => Promise<unknown>) | undefined;

jest.mock("@/controllers/API/api", () => ({
  api: { get: mockApiGet },
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: () => ({
    query: (_key: string[], queryFn: () => Promise<unknown>) => {
      mockQueryFn = queryFn;
      return {};
    },
  }),
}));

jest.mock("@/stores/flowStore", () => ({
  recomputeComponentsToUpdateIfNeeded: jest.fn(),
}));

import { useGetConfig } from "../use-get-config";

describe("useGetConfig", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockQueryFn = undefined;
    useUtilityStore.setState({ catalogGovernanceEnabled: false });
  });

  it("stores the catalog governance flag from public config", async () => {
    mockApiGet.mockResolvedValue({
      data: {
        type: "public",
        frontend_timeout: 30,
        max_file_size_upload: 100,
        event_delivery: EventDeliveryType.STREAMING,
        voice_mode_available: false,
        allow_custom_components: true,
        catalog_governance_enabled: true,
        mcp_base_url: "",
        enable_extension_reload: false,
      },
    });

    renderHook(() => useGetConfig());

    await act(async () => {
      await mockQueryFn?.();
    });

    expect(useUtilityStore.getState().catalogGovernanceEnabled).toBe(true);
  });
});
