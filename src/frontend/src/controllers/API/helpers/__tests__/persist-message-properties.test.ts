import { persistMessageProperties } from "../persist-message-properties";

// Mock dependencies
const mockPut = jest.fn().mockResolvedValue({ data: {} });

jest.mock("@/controllers/API/api", () => ({
  api: {
    put: (...args: unknown[]) => mockPut(...args),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `api/v1/${key.toLowerCase()}`,
}));

jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  isAuthenticatedPlayground: jest.fn(),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: jest.fn(() => ({ playgroundPage: false })),
  },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: jest.fn(() => ({ currentFlowId: "real-flow-id-123" })),
  },
}));

import useFlowStore from "@/stores/flowStore";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";

const mockFlowStore = useFlowStore as unknown as { getState: jest.Mock };
const mockIsAuth = isAuthenticatedPlayground as jest.MockedFunction<
  typeof isAuthenticatedPlayground
>;

const MESSAGE_ID = "msg-abc-123";
const PAYLOAD = { properties: { build_duration: 1500 } };

describe("persistMessageProperties", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPut.mockResolvedValue({ data: {} });
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockIsAuth.mockReturnValue(false);
  });

  // --- Happy path ---

  it("should_use_standard_endpoint_when_not_playground", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockIsAuth.mockReturnValue(false);

    persistMessageProperties(MESSAGE_ID, PAYLOAD);

    expect(mockPut).toHaveBeenCalledTimes(1);
    expect(mockPut).toHaveBeenCalledWith(
      `api/v1/messages/${MESSAGE_ID}`,
      PAYLOAD,
    );
  });

  it("should_use_shared_endpoint_when_authenticated_playground", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockIsAuth.mockReturnValue(true);

    persistMessageProperties(MESSAGE_ID, PAYLOAD);

    expect(mockPut).toHaveBeenCalledTimes(1);
    expect(mockPut).toHaveBeenCalledWith(
      `api/v1/messages/shared/${MESSAGE_ID}`,
      PAYLOAD,
      { params: { source_flow_id: "real-flow-id-123" } },
    );
  });

  it("should_skip_api_call_when_anonymous_playground", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockIsAuth.mockReturnValue(false);

    persistMessageProperties(MESSAGE_ID, PAYLOAD);

    expect(mockPut).not.toHaveBeenCalled();
  });

  // --- Error handling ---

  it("should_not_throw_when_standard_endpoint_fails", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockIsAuth.mockReturnValue(false);
    mockPut.mockRejectedValue(new Error("Network error"));

    expect(() => persistMessageProperties(MESSAGE_ID, PAYLOAD)).not.toThrow();
  });

  it("should_not_throw_when_shared_endpoint_fails", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockIsAuth.mockReturnValue(true);
    mockPut.mockRejectedValue(new Error("404 Not Found"));

    expect(() => persistMessageProperties(MESSAGE_ID, PAYLOAD)).not.toThrow();
  });

  // --- Edge cases ---

  it("should_pass_arbitrary_payload_through_unchanged", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockIsAuth.mockReturnValue(false);
    const complexPayload = {
      text: "hello",
      properties: {
        build_duration: 3000,
        usage: { total_tokens: 100, input_tokens: 40, output_tokens: 60 },
      },
    };

    persistMessageProperties(MESSAGE_ID, complexPayload);

    expect(mockPut).toHaveBeenCalledWith(
      `api/v1/messages/${MESSAGE_ID}`,
      complexPayload,
    );
  });
});
