import useAlertStore from "@/stores/alertStore";
import type { APIClassType, CustomComponentRequest } from "@/types/api";

const mockApiPost = jest.fn();
const mockFlowState: {
  currentFlowId: string | undefined;
  currentFlow: { folder_id?: string } | undefined;
} = {
  currentFlowId: undefined,
  currentFlow: undefined,
};

jest.mock("@/controllers/API/api", () => ({
  api: { post: mockApiPost },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/v1/custom_component"),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  customStringify: (value: unknown) => JSON.stringify(value),
}));

jest.mock("@/stores/flowsManagerStore", () => {
  const store = (selector: (state: typeof mockFlowState) => unknown) =>
    selector(mockFlowState);
  store.getState = () => mockFlowState;
  return { __esModule: true, default: store };
});

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
    mockFlowState.currentFlow = undefined;
    mockApiPost.mockResolvedValue({ data: response });
    useAlertStore.setState({ notificationList: [], tempNotificationList: [] });
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
    expect(useAlertStore.getState().tempNotificationList).toEqual([]);
  });

  it("names unrestored fields and keeps the warning beside a later success", async () => {
    const savedNode: APIClassType = {
      ...frontendNode,
      display_name: "Run Flow",
      template: {
        generated_input: {
          type: "str",
          required: false,
          list: false,
          show: true,
          readonly: false,
          display_name: "Input Text (Chat Input)",
          value: "saved value",
        },
      },
    };
    mockApiPost.mockResolvedValueOnce({
      data: {
        ...response,
        warnings: [
          {
            code: "generated_fields_not_restored",
            fields: ["generated_input", "unlabeled_input", "generated_input"],
            refresh_fields: ["flow_name_selected"],
          },
        ],
      },
    });

    await usePostValidateComponentCode().mutateAsync({
      ...payload,
      frontend_node: savedNode,
    });
    useAlertStore.getState().setSuccessData({ title: "Updated 1 component" });

    expect(useAlertStore.getState().tempNotificationList).toEqual([
      expect.objectContaining({ type: "success" }),
      expect.objectContaining({
        type: "notice",
        title: "Some fields could not be restored in Run Flow",
        list: ["Input Text (Chat Input)", "unlabeled_input"],
      }),
    ]);
  });

  it("keeps each component's warning when bulk validation runs concurrently", async () => {
    mockApiPost.mockResolvedValue({
      data: {
        ...response,
        warnings: [
          {
            code: "generated_fields_not_restored",
            fields: ["name"],
            refresh_fields: ["tool"],
          },
        ],
      },
    });
    const mutation = usePostValidateComponentCode();

    await Promise.all(
      ["First MCP Tools", "Second MCP Tools"].map((display_name) =>
        mutation.mutateAsync({
          ...payload,
          frontend_node: { ...frontendNode, display_name },
        }),
      ),
    );

    expect(useAlertStore.getState().tempNotificationList).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          title: "Some fields could not be restored in First MCP Tools",
        }),
        expect.objectContaining({
          title: "Some fields could not be restored in Second MCP Tools",
        }),
      ]),
    );
  });

  it("names the refresh field when generated fields cannot be identified", async () => {
    mockApiPost.mockResolvedValueOnce({
      data: {
        ...response,
        warnings: [
          {
            code: "generated_fields_not_restored",
            fields: [],
            refresh_fields: ["tool"],
          },
        ],
      },
    });

    await usePostValidateComponentCode().mutateAsync(payload);

    expect(useAlertStore.getState().tempNotificationList).toEqual([
      expect.objectContaining({
        title: "Could not refresh fields in Test Component",
        list: ["tool"],
      }),
    ]);
  });

  it("does not report an empty warning", async () => {
    mockApiPost.mockResolvedValueOnce({
      data: {
        ...response,
        warnings: [
          {
            code: "generated_fields_not_restored",
            fields: [],
            refresh_fields: [],
          },
        ],
      },
    });

    await usePostValidateComponentCode().mutateAsync(payload);

    expect(useAlertStore.getState().tempNotificationList).toEqual([]);
  });

  it("discards an unscoped response after navigation enters a flow", async () => {
    let resolveResponse: ((value: unknown) => void) | undefined;
    mockApiPost.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );
    const mutation = usePostValidateComponentCode();

    const pending = mutation.mutateAsync(payload);
    await Promise.resolve();
    mockFlowState.currentFlowId = "flow-one";
    mockFlowState.currentFlow = { folder_id: "project-one" };
    resolveResponse?.({
      data: {
        ...response,
        warnings: [
          {
            code: "generated_fields_not_restored",
            fields: ["private_field"],
            refresh_fields: ["tool"],
          },
        ],
      },
    });

    await expect(pending).resolves.toBeUndefined();
    expect(useAlertStore.getState().tempNotificationList).toEqual([]);
  });

  it("does not start scoped validation after navigation changes the captured scope", async () => {
    mockFlowState.currentFlowId = "flow-one";
    mockFlowState.currentFlow = { folder_id: "project-one" };
    const mutation = usePostValidateComponentCode();
    mockFlowState.currentFlowId = "flow-two";
    mockFlowState.currentFlow = { folder_id: "project-two" };

    await expect(mutation.mutateAsync(payload)).resolves.toBeUndefined();
    expect(mockApiPost).not.toHaveBeenCalled();
  });

  it("discards a scoped response after the active flow changes", async () => {
    mockFlowState.currentFlowId = "flow-one";
    mockFlowState.currentFlow = { folder_id: "project-one" };
    let resolveResponse: ((value: unknown) => void) | undefined;
    mockApiPost.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );
    const mutation = usePostValidateComponentCode();

    const pending = mutation.mutateAsync(payload);
    await Promise.resolve();
    expect(mockApiPost).toHaveBeenCalledTimes(1);
    mockFlowState.currentFlowId = "flow-two";
    mockFlowState.currentFlow = { folder_id: "project-two" };
    resolveResponse?.({ data: response });

    await expect(pending).resolves.toBeUndefined();
  });

  it("discards a scoped response after the flow moves projects", async () => {
    mockFlowState.currentFlowId = "flow-one";
    mockFlowState.currentFlow = { folder_id: "project-one" };
    let resolveResponse: ((value: unknown) => void) | undefined;
    mockApiPost.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );
    const mutation = usePostValidateComponentCode();

    const pending = mutation.mutateAsync(payload);
    await Promise.resolve();
    mockFlowState.currentFlow = { folder_id: "project-two" };
    resolveResponse?.({ data: response });

    await expect(pending).resolves.toBeUndefined();
  });
});
