import type { APIClassType } from "@/types/api";
import { mutateTemplate } from "../mutate-template";

describe("mutateTemplate", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  it("sends Tool Mode changes immediately", async () => {
    const node = {
      template: {
        code: { value: "component source" },
      },
      outputs: [],
      tool_mode: false,
    } as unknown as APIClassType;
    const updatedNode = {
      template: node.template,
      outputs: [],
      last_updated: "2026-07-21T16:30:00.000Z",
    } as unknown as APIClassType;
    const mutateAsync = jest.fn().mockResolvedValue(updatedNode);
    const setNodeClass = jest.fn();

    await mutateTemplate(
      true,
      "mcp-tools-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "tool_mode",
      jest.fn(),
      true,
    );

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ value: true, tool_mode: true }),
    );
    expect(setNodeClass).toHaveBeenCalledWith(
      expect.objectContaining({ tool_mode: true }),
    );
  });

  it("cancels a stale Toolset metadata refresh when Tool Mode changes", async () => {
    jest.useFakeTimers();
    const node = {
      template: {
        code: { value: "component source" },
        tools_metadata: { value: [{ name: "fetch_content" }] },
      },
      outputs: [{ name: "component_as_tool" }],
      tool_mode: true,
    } as unknown as APIClassType;
    const metadataMutateAsync = jest.fn();
    const toolModeMutateAsync = jest.fn().mockResolvedValue({
      template: node.template,
      outputs: [],
      last_updated: "2026-07-21T16:31:00.000Z",
    });

    await mutateTemplate(
      node.template.tools_metadata.value,
      "url-node",
      node,
      jest.fn(),
      { mutateAsync: metadataMutateAsync } as never,
      jest.fn(),
      "tools_metadata",
      jest.fn(),
      true,
    );

    await mutateTemplate(
      false,
      "url-node",
      node,
      jest.fn(),
      { mutateAsync: toolModeMutateAsync } as never,
      jest.fn(),
      "tool_mode",
      jest.fn(),
      false,
    );
    await jest.runAllTimersAsync();

    expect(toolModeMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ value: false, tool_mode: false }),
    );
    expect(metadataMutateAsync).not.toHaveBeenCalled();
  });
});
