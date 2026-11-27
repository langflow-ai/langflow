import { act, renderHook } from "@testing-library/react";
import type { APIClassType } from "@/types/api";

const mockMutateTemplate = jest.fn();
const mockSetNode = jest.fn();

jest.mock("../../helpers/mutate-template", () => ({
  mutateTemplate: (...args: unknown[]) => mockMutateTemplate(...args),
}));
jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: jest.fn(() => ({ mutateAsync: jest.fn() })),
}));
jest.mock("@/customization/utils/analytics", () => ({ track: jest.fn() }));
jest.mock("@xyflow/react", () => ({ useUpdateNodeInternals: () => jest.fn() }));
jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ takeSnapshot: jest.fn() }),
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setNode: mockSetNode }),
}));

import useHandleOnNewValue from "../use-handle-new-value";

const mcpNode = (): APIClassType =>
  ({
    template: {
      mcp_server: {
        _input_type: "McpInput",
        real_time_refresh: true,
        value: { name: "srv_a", config: {} },
      },
      tool: { value: "vary_queries", options: ["vary_queries"] },
    },
  }) as unknown as APIClassType;

describe("useHandleOnNewValue for an MCP server switch", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockMutateTemplate.mockClear();
    mockSetNode.mockClear();
  });
  afterEach(() => jest.useRealTimers());

  it("tells the backend which server the node had before the switch", async () => {
    const { result } = renderHook(() =>
      useHandleOnNewValue({
        node: mcpNode(),
        nodeId: "mcp-1",
        name: "mcp_server",
      }),
    );

    await act(async () => {
      await result.current.handleOnNewValue({
        value: { name: "srv_b", config: {} },
      });
      jest.runAllTimers();
    });

    const requestNode = mockMutateTemplate.mock.calls[0][2] as APIClassType;
    expect(requestNode.template.mcp_server.value).toEqual({
      name: "srv_b",
      config: {},
    });
    expect(requestNode.template._frontend_node_previous_mcp_server).toEqual({
      value: "srv_a",
    });
  });

  it("keeps the request-only previous server out of the stored node", async () => {
    const { result } = renderHook(() =>
      useHandleOnNewValue({
        node: mcpNode(),
        nodeId: "mcp-1",
        name: "mcp_server",
      }),
    );

    await act(async () => {
      await result.current.handleOnNewValue({
        value: { name: "srv_b", config: {} },
      });
      jest.runAllTimers();
    });

    const update = mockSetNode.mock.calls[0][1];
    const stored =
      typeof update === "function"
        ? update({ id: "mcp-1", data: { node: mcpNode() } })
        : update;
    expect(
      stored.data.node.template._frontend_node_previous_mcp_server,
    ).toBeUndefined();
  });
});
