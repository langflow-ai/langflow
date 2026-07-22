import { render, screen } from "@testing-library/react";
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

describe("DefaultEdge accessibility", () => {
  it("should_have_no_axe_violations_with_named_nodes", async () => {
    setNodes({
      n1: { display_name: "Chat Input" },
      n2: { display_name: "Chat Output" },
    });

    const { container } = render(<DefaultEdge {...baseProps} />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_accessible_name_from_node_display_names", () => {
    setNodes({
      n1: { display_name: "Chat Input" },
      n2: { display_name: "Chat Output" },
    });

    render(<DefaultEdge {...baseProps} />);

    expect(
      screen.getByRole("img", { name: "Edge from Chat Input to Chat Output" }),
    ).toBeInTheDocument();
  });

  it("should_fall_back_to_raw_ids_when_display_name_is_missing", async () => {
    setNodes({ n1: undefined, n2: undefined });

    const { container } = render(<DefaultEdge {...baseProps} />);

    expect(
      screen.getByRole("img", { name: "Edge from n1 to n2" }),
    ).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
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
    expect(
      screen.getByRole("img", { name: "Edge from Chat Input to Chat Output" }),
    ).toBeInTheDocument();
  });
});
