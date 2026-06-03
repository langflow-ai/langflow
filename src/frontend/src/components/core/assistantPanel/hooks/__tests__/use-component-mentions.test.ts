import { act, renderHook } from "@testing-library/react";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType } from "@/types/flow";
import { useComponentMentions } from "../use-component-mentions";

function makeNode(
  id: string,
  type: string,
  displayName: string,
  selected = false,
  template?: Record<string, unknown>,
): AllNodeType {
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    selected,
    data: {
      id,
      type,
      node: { display_name: displayName, icon: "Box", template },
    },
  } as unknown as AllNodeType;
}

let nodes: AllNodeType[] = [];

function seedNodes(seed: AllNodeType[]) {
  nodes = seed;
  useFlowStore.setState({
    nodes,
    reactFlowInstance: null,
    setNodes: (
      update: AllNodeType[] | ((old: AllNodeType[]) => AllNodeType[]),
    ) => {
      nodes = typeof update === "function" ? update(nodes) : update;
      useFlowStore.setState({ nodes });
    },
  });
}

function makeTextarea(selectionStart: number): HTMLTextAreaElement {
  return {
    selectionStart,
    focus: () => {},
    setSelectionRange: () => {},
  } as unknown as HTMLTextAreaElement;
}

function selectedIds(): string[] {
  return useFlowStore
    .getState()
    .nodes.filter((n) => n.selected)
    .map((n) => n.id);
}

describe("useComponentMentions", () => {
  beforeEach(() => {
    seedNodes([
      makeNode("ChatInput-aaa", "ChatInput", "Chat Input"),
      makeNode("OpenAI-bbb", "OpenAIModel", "OpenAI"),
      makeNode("ChatOutput-ccc", "ChatOutput", "Chat Output"),
    ]);
  });

  it("should_open_with_all_components_when_at_typed", () => {
    const { result } = renderHook(() =>
      useComponentMentions({
        value: "@",
        setValue: jest.fn(),
        textareaRef: { current: makeTextarea(1) },
      }),
    );
    act(() => result.current.handleValueChange("@", 1));
    expect(result.current.isOpen).toBe(true);
    expect(result.current.items).toHaveLength(3);
  });

  it("should_filter_components_by_query", () => {
    const { result } = renderHook(() =>
      useComponentMentions({
        value: "@chat",
        setValue: jest.fn(),
        textareaRef: { current: makeTextarea(5) },
      }),
    );
    act(() => result.current.handleValueChange("@chat", 5));
    expect(result.current.items.map((i) => i.id)).toEqual([
      "ChatInput-aaa",
      "ChatOutput-ccc",
    ]);
  });

  it("should_highlight_active_node_on_the_canvas", () => {
    const { result } = renderHook(() =>
      useComponentMentions({
        value: "@open",
        setValue: jest.fn(),
        textareaRef: { current: makeTextarea(5) },
      }),
    );
    act(() => result.current.handleValueChange("@open", 5));
    expect(selectedIds()).toEqual(["OpenAI-bbb"]);
  });

  it("should_insert_quoted_id_token_on_confirm", () => {
    const setValue = jest.fn();
    const { result } = renderHook(() =>
      useComponentMentions({
        value: "@open",
        setValue,
        textareaRef: { current: makeTextarea(5) },
      }),
    );
    act(() => result.current.handleValueChange("@open", 5));
    act(() => result.current.confirm());
    expect(setValue).toHaveBeenCalledWith("'OpenAI-bbb'");
  });

  it("should_cycle_active_index_with_tab", () => {
    const { result } = renderHook(() =>
      useComponentMentions({
        value: "@",
        setValue: jest.fn(),
        textareaRef: { current: makeTextarea(1) },
      }),
    );
    act(() => result.current.handleValueChange("@", 1));
    const tab = {
      key: "Tab",
      shiftKey: false,
      preventDefault: () => {},
    } as unknown as React.KeyboardEvent<HTMLTextAreaElement>;
    act(() => {
      result.current.handleKeyDown(tab);
    });
    expect(result.current.activeIndex).toBe(1);
  });

  it("should_list_fields_when_dot_typed_after_a_token", () => {
    seedNodes([
      makeNode("ChatInput-aaa", "ChatInput", "Chat Input", false, {
        input_value: { display_name: "Input Value", show: true, type: "str" },
        api_key: { display_name: "API Key", show: true, type: "str" },
        code: { show: true, type: "code" },
        hidden: { display_name: "Hidden", show: false, type: "str" },
        _type: "ChatInput",
      }),
    ]);
    const value = "'ChatInput-aaa'.";
    const { result } = renderHook(() =>
      useComponentMentions({
        value,
        setValue: jest.fn(),
        textareaRef: { current: makeTextarea(value.length) },
      }),
    );
    act(() => result.current.handleValueChange(value, value.length));
    expect(result.current.isOpen).toBe(true);
    // code / _type / show:false are excluded; field display names are shown.
    expect(result.current.items.map((i) => i.displayName)).toEqual([
      "Input Value",
      "API Key",
    ]);
    expect(result.current.items.every((i) => i.kind === "field")).toBe(true);
  });

  it("should_filter_fields_by_query_after_the_dot", () => {
    seedNodes([
      makeNode("ChatInput-aaa", "ChatInput", "Chat Input", false, {
        input_value: { display_name: "Input Value", show: true, type: "str" },
        api_key: { display_name: "API Key", show: true, type: "str" },
      }),
    ]);
    const value = "'ChatInput-aaa'.api";
    const { result } = renderHook(() =>
      useComponentMentions({
        value,
        setValue: jest.fn(),
        textareaRef: { current: makeTextarea(value.length) },
      }),
    );
    act(() => result.current.handleValueChange(value, value.length));
    expect(result.current.items.map((i) => i.id)).toEqual(["api_key"]);
  });

  it("should_insert_component_dot_field_token_on_confirm", () => {
    seedNodes([
      makeNode("ChatInput-aaa", "ChatInput", "Chat Input", false, {
        input_value: { display_name: "Input Value", show: true, type: "str" },
      }),
    ]);
    const value = "'ChatInput-aaa'.";
    const setValue = jest.fn();
    const { result } = renderHook(() =>
      useComponentMentions({
        value,
        setValue,
        textareaRef: { current: makeTextarea(value.length) },
      }),
    );
    act(() => result.current.handleValueChange(value, value.length));
    act(() => result.current.confirm());
    expect(setValue).toHaveBeenCalledWith("'ChatInput-aaa.input_value' ");
  });

  it("should_restore_prior_selection_on_escape", () => {
    seedNodes([
      makeNode("ChatInput-aaa", "ChatInput", "Chat Input", true),
      makeNode("OpenAI-bbb", "OpenAIModel", "OpenAI"),
    ]);
    const { result } = renderHook(() =>
      useComponentMentions({
        value: "@open",
        setValue: jest.fn(),
        textareaRef: { current: makeTextarea(5) },
      }),
    );
    act(() => result.current.handleValueChange("@open", 5));
    expect(selectedIds()).toEqual(["OpenAI-bbb"]);
    const esc = {
      key: "Escape",
      preventDefault: () => {},
    } as unknown as React.KeyboardEvent<HTMLTextAreaElement>;
    act(() => {
      result.current.handleKeyDown(esc);
    });
    expect(selectedIds()).toEqual(["ChatInput-aaa"]);
    expect(result.current.isOpen).toBe(false);
  });
});
