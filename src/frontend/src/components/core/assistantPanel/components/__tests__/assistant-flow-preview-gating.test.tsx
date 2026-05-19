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
    it("should_render_primary_apply_button_when_status_is_pending", () => {
      // Pre-FP3 this was the single 'Continue' button with testid
      // `assistant-flow-continue-button`. Post-FP3 the primary acceptance
      // is 'Add to canvas' (non-destructive default). The test was
      // renamed to match the new contract.
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-flow-add-button"),
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

    it("should_call_onApply_with_add_when_primary_button_clicked", () => {
      // Renamed from "should_call_onApply_when_continue_button_clicked"
      // to match the FP3 dual-action card. The primary acceptance is
      // now 'Add to canvas' (mode='add').
      const onApply = jest.fn();
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={onApply}
          onDismiss={jest.fn()}
        />,
      );

      fireEvent.click(screen.getByTestId("assistant-flow-add-button"));
      expect(onApply).toHaveBeenCalledTimes(1);
      expect(onApply).toHaveBeenCalledWith("add");
    });

    it("should_render_add_to_canvas_button_when_pending", () => {
      // Dual-action card: 'Add to canvas' is always available so the
      // user can preserve existing canvas state. The destructive
      // 'Replace canvas' is the secondary action.
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-flow-add-button"),
      ).toBeInTheDocument();
    });

    it("should_render_replace_canvas_button_when_pending", () => {
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      // The legacy 'Continue' button is rebranded as 'Replace canvas'
      // for clarity. We address it via a dedicated testid so the role
      // is explicit in tests.
      expect(
        screen.getByTestId("assistant-flow-replace-button"),
      ).toBeInTheDocument();
    });

    it("should_call_onApply_with_add_when_add_button_clicked", () => {
      const onApply = jest.fn();
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={onApply}
          onDismiss={jest.fn()}
        />,
      );

      fireEvent.click(screen.getByTestId("assistant-flow-add-button"));
      expect(onApply).toHaveBeenCalledTimes(1);
      expect(onApply).toHaveBeenCalledWith("add");
    });

    it("should_call_onApply_with_replace_when_replace_button_clicked", () => {
      const onApply = jest.fn();
      render(
        <AssistantFlowPreview
          flowPreview={SAMPLE_PREVIEW}
          status="pending"
          onApply={onApply}
          onDismiss={jest.fn()}
        />,
      );

      fireEvent.click(screen.getByTestId("assistant-flow-replace-button"));
      expect(onApply).toHaveBeenCalledTimes(1);
      expect(onApply).toHaveBeenCalledWith("replace");
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

      fireEvent.click(screen.getByTestId("assistant-flow-add-button"));
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
        screen.queryByTestId("assistant-flow-add-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("assistant-flow-replace-button"),
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
        screen.queryByTestId("assistant-flow-add-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("assistant-flow-replace-button"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("assistant-flow-dismiss-button"),
      ).not.toBeInTheDocument();
    });
  });

  describe("large-flow preview gating (> 7 components)", () => {
    function previewWith(nodeCount: number) {
      const nodes = Array.from({ length: nodeCount }, (_, i) => ({
        id: `n${i}`,
        position: { x: i * 100, y: 0 },
        data: { type: `Comp${i}` },
      }));
      return {
        flow: { name: "Big", data: { nodes, edges: [] } },
        name: "Big",
        nodeCount,
        edgeCount: 0,
        graph: "",
      };
    }

    it("should_render_preview_canvas_when_7_or_fewer_components", () => {
      render(
        <AssistantFlowPreview
          flowPreview={previewWith(7)}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(screen.getByTestId("react-flow-mock")).toBeInTheDocument();
      expect(
        screen.queryByText(/too many components/i),
      ).not.toBeInTheDocument();
    });

    it("should_hide_preview_canvas_and_show_notice_when_more_than_7_components", () => {
      render(
        <AssistantFlowPreview
          flowPreview={previewWith(8)}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(screen.queryByTestId("react-flow-mock")).not.toBeInTheDocument();
      expect(screen.getByText(/too many components/i)).toBeInTheDocument();
    });

    it("should_keep_action_buttons_even_when_preview_is_disabled", () => {
      render(
        <AssistantFlowPreview
          flowPreview={previewWith(20)}
          status="pending"
          onApply={jest.fn()}
          onDismiss={jest.fn()}
        />,
      );
      expect(
        screen.getByTestId("assistant-flow-add-button"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("assistant-flow-dismiss-button"),
      ).toBeInTheDocument();
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
