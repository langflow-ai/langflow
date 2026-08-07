import useFlowStore from "@/stores/flowStore";
import type { APIClassType } from "@/types/api";
import { mutateTemplate } from "../mutate-template";

const setStoreNodeCode = (nodeId: string, code: string) => {
  jest.spyOn(useFlowStore, "getState").mockReturnValue({
    nodes: [
      { id: nodeId, data: { node: { template: { code: { value: code } } } } },
    ],
  } as never);
};

describe("mutateTemplate", () => {
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
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

  it("drops a refresh whose component code was replaced while it was in flight", async () => {
    const node = {
      template: {
        code: { value: "original source" },
        base_url: { value: "http://localhost:11434" },
      },
      outputs: [],
    } as unknown as APIClassType;
    const setNodeClass = jest.fn();
    const callback = jest.fn();
    const mutateAsync = jest.fn().mockImplementation(async () => {
      setStoreNodeCode("ollama-node", "edited source");
      return {
        template: { code: { value: "original source" } },
        outputs: [],
      } as unknown as APIClassType;
    });
    setStoreNodeCode("ollama-node", "original source");

    await mutateTemplate(
      node.template.base_url.value,
      "ollama-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "base_url",
      callback,
    );
    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(mutateAsync).toHaveBeenCalled();
    expect(setNodeClass).not.toHaveBeenCalled();
    expect(callback).toHaveBeenCalled();
  });

  it("applies a refresh while the component code is unchanged", async () => {
    const node = {
      template: {
        code: { value: "original source" },
        base_url: { value: "http://localhost:11434" },
      },
      outputs: [],
    } as unknown as APIClassType;
    const setNodeClass = jest.fn();
    const mutateAsync = jest.fn().mockResolvedValue({
      template: {
        code: { value: "original source" },
        model_name: { value: "" },
      },
      outputs: [],
    } as unknown as APIClassType);
    setStoreNodeCode("unchanged-node", "original source");

    await mutateTemplate(
      node.template.base_url.value,
      "unchanged-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "base_url",
    );
    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(setNodeClass).toHaveBeenCalledWith(
      expect.objectContaining({
        template: expect.objectContaining({ model_name: expect.anything() }),
      }),
    );
  });
});
