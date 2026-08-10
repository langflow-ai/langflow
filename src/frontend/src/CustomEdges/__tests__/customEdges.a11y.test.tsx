import { render } from "@testing-library/react";
import type { EdgeProps } from "@xyflow/react";
import { ReactFlowProvider } from "@xyflow/react";
import { axe } from "@/utils/a11y-test";
import { DefaultEdge } from "..";

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      getNode: () => undefined,
      edges: [],
      setEdges: jest.fn(),
    }),
}));

// scapedJSONStringfy encodes the handle payload with œ standing in for
// quotes (see utils/reactflowUtils.ts) — this is a minimal target handle
// with no output_types, matching the component's non-loop path.
const targetHandleId = "{œfieldNameœ:œfooœ,œidœ:œtarget-nodeœ}";

const baseProps = {
  id: "edge-1",
  source: "source-node",
  target: "target-node",
  sourceHandleId: null,
  targetHandleId,
  sourceX: 0,
  sourceY: 0,
  targetX: 100,
  targetY: 100,
  sourcePosition: "right",
  targetPosition: "left",
  animated: false,
  selectable: true,
  deletable: true,
  selected: false,
} as unknown as EdgeProps;

describe("DefaultEdge", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <ReactFlowProvider>
        <svg>
          <DefaultEdge {...baseProps} />
        </svg>
      </ReactFlowProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
