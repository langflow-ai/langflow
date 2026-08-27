import type { APIClassType, CustomComponentRequest } from "@/types/api";

const mockApiPost = jest.fn();
const mockFlowState: { currentFlowId: string | undefined } = {
  currentFlowId: undefined,
};

jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/custom_component"),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof mockFlowState) => unknown) =>
    selector(mockFlowState),
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn(
      (_key: unknown, mutationFn: (payload: unknown) => Promise<unknown>) => ({
        mutateAsync: mutationFn,
      }),
    ),
  })),
}));

import { usePostValidateComponentCode } from "../use-post-validate-component-code";

const frontendNode: APIClassType = {
  description: "Test component",
  display_name: "Test Component",
  documentation: "https://example.test/component",
  template: {},
};

const payload = {
  code: "class TestComponent: pass",
  frontend_node: frontendNode,
};

const response: CustomComponentRequest = {
  data: frontendNode,
  type: "TestComponent",
};

describe("usePostValidateComponentCode provider scope", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFlowState.currentFlowId = undefined;
    mockApiPost.mockResolvedValue({ data: response });
  });

  it("appends the trusted current flow to component validation", async () => {
    mockFlowState.currentFlowId = "flow-one";

    const mutation = usePostValidateComponentCode();
    await mutation.mutateAsync(payload);

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/custom_component?flow_id=flow-one",
      payload,
    );
  });

  it("keeps component validation unscoped outside a flow", async () => {
    const mutation = usePostValidateComponentCode();
    await mutation.mutateAsync(payload);

    expect(mockApiPost).toHaveBeenCalledWith(
      "/api/v1/custom_component",
      payload,
    );
  });
});
