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

  it.each([
    {
      selected: "greet",
      options: ["greet"],
      toolMode: false,
      refreshes: false,
    },
    { selected: "", options: ["greet"], toolMode: false, refreshes: true },
    {
      selected: "old-tool",
      options: ["greet"],
      toolMode: false,
      refreshes: true,
    },
    { selected: "greet", options: [], toolMode: false, refreshes: true },
    { selected: "greet", options: ["greet"], toolMode: true, refreshes: true },
  ])(
    "retains saved MCP selection on mount with $selected, $options, tool mode $toolMode",
    ({ selected, options, toolMode, refreshes }) => {
      const node = {
        tool_mode: toolMode,
        template: {
          mcp_server: {
            _input_type: "McpInput",
            real_time_refresh: true,
            value: { name: "saved-server" },
          },
          tool: { value: selected, options },
        },
      } as unknown as APIClassType;
      renderHook(() =>
        useFetchDataOnMount(
          node,
          "node-1",
          jest.fn(),
          "mcp_server",
          {} as never,
        ),
      );

      expect(mockMutateTemplate).toHaveBeenCalledTimes(refreshes ? 1 : 0);
    },
  );

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
