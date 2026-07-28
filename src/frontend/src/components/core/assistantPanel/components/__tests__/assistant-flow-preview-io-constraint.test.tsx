import { render, screen } from "@testing-library/react";
import { AssistantFlowPreview } from "../assistant-flow-preview";

jest.mock("@xyflow/react", () => ({
  __esModule: true,
  ReactFlow: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="react-flow-mock">{children}</div>
  ),
  ReactFlowProvider: ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  ),
  Background: () => null,
}));

let canvasNodes: { id: string; data?: { type?: string } }[] = [];
jest.mock("@/stores/flowStore", () => {
  const fn = (selector?: (s: Record<string, unknown>) => unknown) => {
    const state = { paste: jest.fn(), nodes: canvasNodes };
    return selector ? selector(state) : state;
  };
  fn.getState = () => ({ paste: jest.fn(), nodes: canvasNodes });
  return { __esModule: true, default: fn };
});

function previewWith(types: string[]) {
  return {
    flow: {
      name: "Proposal",
      data: {
        nodes: types.map((type, i) => ({
          id: `${type}-${i}`,
          position: { x: i * 200, y: 0 },
          data: { type },
        })),
        edges: [],
      },
    },
    name: "Proposal",
    nodeCount: types.length,
    edgeCount: 0,
    graph: "",
  };
}

function node(id: string, type: string) {
  return { id, data: { type } };
}

describe("AssistantFlowPreview flow-IO constraints", () => {
  beforeEach(() => {
    canvasNodes = [];
  });

  it("should_offer_add_to_canvas_when_canvas_has_no_flow_input", () => {
    canvasNodes = [node("a", "ChatOutput")];
    render(
      <AssistantFlowPreview
        flowPreview={previewWith(["ChatInput", "ChatOutput"])}
        status="pending"
        onApply={jest.fn()}
        onDismiss={jest.fn()}
      />,
    );
    expect(screen.getByTestId("assistant-flow-add-button")).toBeInTheDocument();
    expect(
      screen.getByTestId("assistant-flow-replace-button"),
    ).toBeInTheDocument();
  });

  it("should_hide_add_to_canvas_when_proposal_chat_input_duplicates_canvas_chat_input", () => {
    canvasNodes = [node("a", "ChatInput")];
    render(
      <AssistantFlowPreview
        flowPreview={previewWith(["ChatInput", "ChatOutput"])}
        status="pending"
        onApply={jest.fn()}
        onDismiss={jest.fn()}
      />,
    );
    expect(
      screen.queryByTestId("assistant-flow-add-button"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("assistant-flow-replace-button"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("assistant-flow-dismiss-button"),
    ).toBeInTheDocument();
  });

  it("should_hide_add_to_canvas_when_proposal_webhook_conflicts_with_canvas_chat_input", () => {
    canvasNodes = [node("a", "ChatInput")];
    render(
      <AssistantFlowPreview
        flowPreview={previewWith(["Webhook", "ChatOutput"])}
        status="pending"
        onApply={jest.fn()}
        onDismiss={jest.fn()}
      />,
    );
    expect(
      screen.queryByTestId("assistant-flow-add-button"),
    ).not.toBeInTheDocument();
  });

  it("should_hide_add_to_canvas_when_proposal_chat_input_conflicts_with_canvas_webhook", () => {
    canvasNodes = [node("a", "Webhook")];
    render(
      <AssistantFlowPreview
        flowPreview={previewWith(["ChatInput"])}
        status="pending"
        onApply={jest.fn()}
        onDismiss={jest.fn()}
      />,
    );
    expect(
      screen.queryByTestId("assistant-flow-add-button"),
    ).not.toBeInTheDocument();
  });

  it("should_explain_why_add_to_canvas_is_unavailable", () => {
    canvasNodes = [node("a", "ChatInput")];
    render(
      <AssistantFlowPreview
        flowPreview={previewWith(["ChatInput"])}
        status="pending"
        onApply={jest.fn()}
        onDismiss={jest.fn()}
      />,
    );
    expect(
      screen.getByTestId("assistant-flow-replace-only-notice"),
    ).toBeInTheDocument();
  });

  it("should_offer_add_to_canvas_when_proposal_has_no_constrained_component", () => {
    canvasNodes = [node("a", "ChatInput")];
    render(
      <AssistantFlowPreview
        flowPreview={previewWith(["Agent", "ChatOutput"])}
        status="pending"
        onApply={jest.fn()}
        onDismiss={jest.fn()}
      />,
    );
    expect(screen.getByTestId("assistant-flow-add-button")).toBeInTheDocument();
    expect(
      screen.queryByTestId("assistant-flow-replace-only-notice"),
    ).not.toBeInTheDocument();
  });
});
