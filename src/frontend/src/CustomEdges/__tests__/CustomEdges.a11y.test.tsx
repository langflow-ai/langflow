import { render } from "@testing-library/react";
import { Position } from "@xyflow/react";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType } from "@/types/flow";
import type { FlowStoreType } from "@/types/zustand/flow";
import { axe } from "@/utils/a11y-test";
import { DefaultEdge } from "../index";

function setNodes(
  nodes: Record<string, { display_name?: string } | undefined>,
) {
  useFlowStore.setState({
    getNode: (id: string) => {
      const node = nodes[id];
      if (node === undefined) return undefined;
      return {
        id,
        position: { x: 0, y: 0 },
        data: { node: { display_name: node.display_name } },
      } as unknown as AllNodeType;
    },
    edges: [],
    setEdges: jest.fn(),
  } as Partial<FlowStoreType>);
}

const baseProps = {
  id: "e1",
  source: "n1",
  target: "n2",
  sourceX: 0,
  sourceY: 0,
  targetX: 100,
  targetY: 100,
  sourceHandleId: "sh",
  targetHandleId: JSON.stringify({ fieldName: "x" }),
  sourcePosition: Position.Right,
  targetPosition: Position.Left,
};

// The accessible name for an edge now comes from `edge.ariaLabel`, set once
// at build time in PageComponent (see get-edge-aria-label.ts) and read
// natively by ReactFlow's EdgeWrapper <g>. DefaultEdge itself must NOT
// render a competing role/aria-label on its interaction path: doing so
// either duplicates the wrapper's name (editable canvas, wrapper is
// role="group" and focusable) or is silently dropped (locked/preview,
// wrapper is role="img" and its subtree is pruned from the a11y tree).
describe("DefaultEdge accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    setNodes({
      n1: { display_name: "Chat Input" },
      n2: { display_name: "Chat Output" },
    });

    const { container } = render(<DefaultEdge {...baseProps} />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("does_not_render_its_own_role_or_aria_label_on_the_interaction_path", () => {
    setNodes({
      n1: { display_name: "Chat Input" },
      n2: { display_name: "Chat Output" },
    });

    const { container } = render(<DefaultEdge {...baseProps} />);
    const interactionPath = container.querySelector(
      '[data-testid="edge-context-menu-trigger"]',
    );

    expect(interactionPath).not.toBeNull();
    expect(interactionPath).not.toHaveAttribute("role");
    expect(interactionPath).not.toHaveAttribute("aria-label");
  });

  it("should_stay_accessible_when_selected_and_animated", async () => {
    setNodes({
      n1: { display_name: "Chat Input" },
      n2: { display_name: "Chat Output" },
    });

    const { container } = render(
      <DefaultEdge {...baseProps} selected animated deletable selectable />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
