import { renderHook } from "@testing-library/react";
import type { APIClassType } from "@/types/api";

const mockMutateTemplate = jest.fn();

jest.mock("../../helpers/mutate-template", () => ({
  mutateTemplate: (...args: unknown[]) => mockMutateTemplate(...args),
}));

jest.mock("../../../stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));

import useFetchDataOnMount from "../use-fetch-data-on-mount";

const nodeWithRefreshableField = (): APIClassType =>
  ({
    template: {
      model_name: {
        real_time_refresh: true,
        options: [],
        value: "",
      },
    },
  }) as unknown as APIClassType;

const mcpNode = (
  server: string,
  tool: string,
  options: string[] = [tool],
  toolMode = false,
): APIClassType =>
  ({
    tool_mode: toolMode,
    template: {
      mcp_server: {
        type: "mcp",
        real_time_refresh: true,
        value: { name: server, config: {} },
      },
      tool: { value: tool, options },
    },
  }) as unknown as APIClassType;

describe("useFetchDataOnMount", () => {
  beforeEach(() => mockMutateTemplate.mockClear());

  it("refreshes the template on mount", () => {
    renderHook(() =>
      useFetchDataOnMount(
        nodeWithRefreshableField(),
        "node-1",
        jest.fn(),
        "model_name",
        {} as never,
      ),
    );

    expect(mockMutateTemplate).toHaveBeenCalledTimes(1);
  });

  it("keeps saved tool templates when opening MCP nodes on different servers", () => {
    const firstNode = mcpNode("catalog", "list_items");
    const secondNode = mcpNode("search", "find_matches");

    renderHook(() => {
      useFetchDataOnMount(
        firstNode,
        "mcp-1",
        jest.fn(),
        "mcp_server",
        {} as never,
      );
      useFetchDataOnMount(
        secondNode,
        "mcp-2",
        jest.fn(),
        "mcp_server",
        {} as never,
      );
    });

    expect(mockMutateTemplate).not.toHaveBeenCalled();
  });

  it.each([
    ["without a selected tool", "", [], false],
    [
      "with a selected tool missing from its options",
      "old_tool",
      ["list_items"],
      false,
    ],
    ["in tool mode", "list_items", ["list_items"], true],
  ])("refreshes an MCP server %s", (_, tool, options, toolMode) => {
    const node = mcpNode("catalog", tool, options, toolMode);

    renderHook(() =>
      useFetchDataOnMount(node, "mcp-1", jest.fn(), "mcp_server", {} as never),
    );

    expect(mockMutateTemplate).toHaveBeenCalledTimes(1);
    expect(mockMutateTemplate.mock.calls[0][0]).toEqual({
      name: "catalog",
      config: {},
    });
  });

  // Whether that refresh saves the flow is decided by the setter the caller
  // hands in - NodeInputField passes the non-saving one (#8995), covered in
  // use-handle-node-class.test.ts. This hook must pass it through untouched.
  it("applies the refresh through the setter it was given", () => {
    const setNodeClass = jest.fn();

    renderHook(() =>
      useFetchDataOnMount(
        nodeWithRefreshableField(),
        "node-1",
        setNodeClass,
        "model_name",
        {} as never,
      ),
    );

    expect(mockMutateTemplate.mock.calls[0][3]).toBe(setNodeClass);
  });
});
