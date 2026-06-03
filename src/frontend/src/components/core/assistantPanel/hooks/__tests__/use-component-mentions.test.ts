import { act, renderHook } from "@testing-library/react";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType } from "@/types/flow";
import { useComponentMentions } from "../use-component-mentions";

function makeNode(
  id: string,
  type: string,
  displayName: string,
  selected = false,
): AllNodeType {
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    selected,
    data: {
      id,
      type,
      node: { display_name: displayName, icon: "Box" },
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
    expect(setValue).toHaveBeenCalledWith("'OpenAI-bbb' ");
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
