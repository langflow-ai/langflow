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

const setStoreNodeTemplate = (nodeId: string, template: object) => {
  jest.spyOn(useFlowStore, "getState").mockReturnValue({
    nodes: [{ id: nodeId, data: { node: { template } } }],
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
      expect.objectContaining({
        value: true,
        template: node.template,
        tool_mode: true,
      }),
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

  it("keeps a canvas-visibility flip that happened while the refresh was in flight", async () => {
    const node = {
      template: {
        code: { value: "original source" },
        agent_llm: { value: "OpenAI" },
        add_calculator_tool: { value: true, advanced: true },
      },
      outputs: [],
    } as unknown as APIClassType;
    const setNodeClass = jest.fn();
    const mutateAsync = jest.fn().mockImplementation(async () => {
      // The user adds the parameter to the canvas before the response lands.
      setStoreNodeTemplate("agent-node", {
        code: { value: "original source" },
        agent_llm: { value: "OpenAI" },
        add_calculator_tool: { value: true, advanced: false },
      });
      return {
        template: {
          code: { value: "original source" },
          agent_llm: { value: "OpenAI" },
          add_calculator_tool: { value: true, advanced: true },
        },
        outputs: [],
      } as unknown as APIClassType;
    });
    setStoreNodeTemplate("agent-node", node.template);

    await mutateTemplate(
      "OpenAI",
      "agent-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "agent_llm",
    );
    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(setNodeClass).toHaveBeenCalledWith(
      expect.objectContaining({
        template: expect.objectContaining({
          add_calculator_tool: expect.objectContaining({ advanced: false }),
        }),
      }),
    );
  });

  it("keeps an API-exposure flip that happened while the refresh was in flight", async () => {
    const node = {
      template: {
        code: { value: "original source" },
        agent_llm: { value: "OpenAI" },
        max_tokens: { value: 100, api_editable: false },
      },
      outputs: [],
    } as unknown as APIClassType;
    const setNodeClass = jest.fn();
    const mutateAsync = jest.fn().mockImplementation(async () => {
      setStoreNodeTemplate("agent-node", {
        code: { value: "original source" },
        agent_llm: { value: "OpenAI" },
        max_tokens: { value: 100, api_editable: true },
      });
      return {
        template: {
          code: { value: "original source" },
          agent_llm: { value: "OpenAI" },
          max_tokens: { value: 100, api_editable: false },
        },
        outputs: [],
      } as unknown as APIClassType;
    });
    setStoreNodeTemplate("agent-node", node.template);

    await mutateTemplate(
      "OpenAI",
      "agent-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "agent_llm",
    );
    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(setNodeClass).toHaveBeenCalledWith(
      expect.objectContaining({
        template: expect.objectContaining({
          max_tokens: expect.objectContaining({ api_editable: true }),
        }),
      }),
    );
  });

  it("keeps a tool action edited while the refresh was in flight (LE-2272)", async () => {
    const preEdit = [
      {
        name: "fetch_content",
        description: "Fetch content from one or more web pages.",
        approval_actions: [],
        status: true,
      },
    ];
    const edited = [
      {
        name: "web_fetch",
        description: "custom description",
        approval_actions: ["approve", "reject"],
        status: true,
      },
    ];
    const node = {
      template: {
        code: { value: "original source" },
        tools_metadata: { value: preEdit },
      },
      outputs: [],
    } as unknown as APIClassType;
    const setNodeClass = jest.fn();
    // The editor closes while the request is in flight, so the store already
    // holds the edits by the time the pre-edit response lands.
    const mutateAsync = jest.fn().mockImplementation(async () => {
      setStoreNodeTemplate("url-node", {
        code: { value: "original source" },
        tools_metadata: { value: edited },
      });
      return {
        template: {
          code: { value: "original source" },
          tools_metadata: { value: preEdit },
        },
        outputs: [],
      } as unknown as APIClassType;
    });
    setStoreNodeTemplate("url-node", node.template);

    await mutateTemplate(
      preEdit,
      "url-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "tools_metadata",
    );
    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(setNodeClass).toHaveBeenCalledWith(
      expect.objectContaining({
        template: expect.objectContaining({
          tools_metadata: expect.objectContaining({ value: edited }),
        }),
      }),
    );
  });

  it("applies a backend-driven value change the user did not touch", async () => {
    const node = {
      template: {
        code: { value: "original source" },
        agent_llm: { value: "OpenAI" },
        model_name: { value: "gpt-4" },
      },
      outputs: [],
    } as unknown as APIClassType;
    const setNodeClass = jest.fn();
    const mutateAsync = jest.fn().mockResolvedValue({
      template: {
        code: { value: "original source" },
        agent_llm: { value: "OpenAI" },
        model_name: { value: "gpt-5" },
      },
      outputs: [],
    } as unknown as APIClassType);
    setStoreNodeTemplate("agent-node", node.template);

    await mutateTemplate(
      "OpenAI",
      "agent-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "agent_llm",
    );
    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(setNodeClass).toHaveBeenCalledWith(
      expect.objectContaining({
        template: expect.objectContaining({
          model_name: expect.objectContaining({ value: "gpt-5" }),
        }),
      }),
    );
  });

  it("applies a backend-driven visibility change the user did not touch", async () => {
    const node = {
      template: {
        code: { value: "original source" },
        agent_llm: { value: "OpenAI" },
        api_key: { value: "", advanced: true },
      },
      outputs: [],
    } as unknown as APIClassType;
    const setNodeClass = jest.fn();
    const mutateAsync = jest.fn().mockResolvedValue({
      template: {
        code: { value: "original source" },
        agent_llm: { value: "OpenAI" },
        api_key: { value: "", advanced: false },
      },
      outputs: [],
    } as unknown as APIClassType);
    setStoreNodeTemplate("agent-node", node.template);

    await mutateTemplate(
      "OpenAI",
      "agent-node",
      node,
      setNodeClass,
      { mutateAsync } as never,
      jest.fn(),
      "agent_llm",
    );
    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(setNodeClass).toHaveBeenCalledWith(
      expect.objectContaining({
        template: expect.objectContaining({
          api_key: expect.objectContaining({ advanced: false }),
        }),
      }),
    );
  });
});
