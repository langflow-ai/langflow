import { fireEvent, render, screen } from "@testing-library/react";
import { AssistantFlowPreview } from "../assistant-flow-preview";

// AssistantFlowPreview renders a mini ReactFlow canvas; mock the heavy
// internals — we only care about the surrounding card UI for these tests.
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

const mockPaste = jest.fn();
jest.mock("@/stores/flowStore", () => {
  const state = { paste: (...args: unknown[]) => mockPaste(...args) };
  const fn = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  fn.getState = () => state;
  return { __esModule: true, default: fn };
});

const SAMPLE_PREVIEW = {
  flow: {
    name: "Test Flow",
    data: {
      nodes: [
        { id: "n1", position: { x: 0, y: 0 }, data: { type: "ChatInput" } },
        { id: "n2", position: { x: 200, y: 0 }, data: { type: "ChatOutput" } },
      ],
      edges: [{ id: "e1", source: "n1", target: "n2" }],
    },
  },
  name: "Test Flow",
  nodeCount: 2,
  edgeCount: 1,
  graph: "",
};

describe("AssistantFlowPreview gating", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("pending status (Continue gate)", () => {
    it("should_render_continue_button_when_status_is_pending", () => {
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-flow-continue-button"),
      ).toBeInTheDocument();
    });

    it("should_render_dismiss_button_when_status_is_pending", () => {
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-flow-dismiss-button"),
      ).toBeInTheDocument();
    });

    it("should_call_onApply_when_continue_button_clicked", () => {
      const onApply = jest.fn();
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={onApply}
          onDismiss={jest.fn()}
        />,
      );

      fireEvent.click(screen.getByTestId("assistant-flow-continue-button"));
      expect(onApply).toHaveBeenCalledTimes(1);
    });

    it("should_call_onDismiss_when_dismiss_button_clicked", () => {
      const onDismiss = jest.fn();
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={jest.fn()}
          onDismiss={onDismiss}
        />,
      );

      fireEvent.click(screen.getByTestId("assistant-flow-dismiss-button"));
      expect(onDismiss).toHaveBeenCalledTimes(1);
    });

    it("should_not_call_paste_when_continue_clicked", () => {
      // Continue must delegate to onApply (which replays via the hook),
      // NEVER call the legacy paste() path that bypasses node-internals
      // refresh and selected_output mirroring.
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );

      fireEvent.click(screen.getByTestId("assistant-flow-continue-button"));
      expect(mockPaste).not.toHaveBeenCalled();
    });
  });

  describe("applied status", () => {
    it("should_show_added_to_canvas_when_status_is_applied", () => {
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="applied"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(screen.getByText(/added to canvas/i)).toBeInTheDocument();
    });

    it("should_not_render_action_buttons_when_status_is_applied", () => {
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="applied"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.queryByTestId("assistant-flow-continue-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("assistant-flow-dismiss-button"),
      ).not.toBeInTheDocument();
    });
  });

  describe("dismissed status", () => {
    it("should_show_dismissed_label_when_status_is_dismissed", () => {
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="dismissed"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(screen.getByText(/dismissed/i)).toBeInTheDocument();
    });

    it("should_not_render_action_buttons_when_status_is_dismissed", () => {
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="dismissed"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.queryByTestId("assistant-flow-continue-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("assistant-flow-dismiss-button"),
      ).not.toBeInTheDocument();
    });
  });

  describe("legacy path (no status prop)", () => {
    it("should_keep_legacy_add_to_flow_button_when_status_is_undefined", () => {
      // Backward compat: existing callers that don't pass status still get
      // the original "Add to Flow" + paste() behavior.
      render(<AssistantFlowPreview flowPreview={SAMPLE_PREVIEW} />);
      expect(screen.getByText(/add to flow/i)).toBeInTheDocument();
    });
  });
});
