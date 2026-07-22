import { render, screen } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import useFlowStore from "@/stores/flowStore";
import type { APIDataType } from "@/types/api";
import type { FlowStoreType } from "@/types/zustand/flow";
import { axe } from "@/utils/a11y-test";
import HandleRenderComponent from "../index";

function resetFlowStore() {
  useFlowStore.setState({
    nodes: [],
    edges: [],
    handleDragging: undefined,
    filterType: undefined,
  } as Partial<FlowStoreType>);
}

const baseProps = {
  title: "Message",
  myData: {} as unknown as APIDataType,
  colors: [],
  setFilterEdge: jest.fn(),
  testIdComplement: "chatinput-noshownode",
  nodeId: "ChatInput-abc123",
};

describe("HandleRenderComponent accessibility", () => {
  beforeEach(() => {
    resetFlowStore();
  });

  it("should_have_no_axe_violations_for_input_handle", async () => {
    const { container } = render(
      <ReactFlowProvider>
        <HandleRenderComponent {...baseProps} left={true} showNode={true} />
      </ReactFlowProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations_for_output_handle", async () => {
    const { container } = render(
      <ReactFlowProvider>
        <HandleRenderComponent {...baseProps} left={false} showNode={true} />
      </ReactFlowProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_distinct_accessible_names_for_input_and_output", () => {
    const { unmount } = render(
      <ReactFlowProvider>
        <HandleRenderComponent {...baseProps} left={true} showNode={true} />
      </ReactFlowProvider>,
    );
    expect(
      screen.getByLabelText(
        "Input handle for Message on node ChatInput-abc123",
      ),
    ).toBeInTheDocument();
    unmount();

    render(
      <ReactFlowProvider>
        <HandleRenderComponent {...baseProps} left={false} showNode={true} />
      </ReactFlowProvider>,
    );
    expect(
      screen.getByLabelText(
        "Output handle for Message on node ChatInput-abc123",
      ),
    ).toBeInTheDocument();
  });

  it("should_expose_an_accessible_name_when_minimized_with_proxy_handle_top", async () => {
    const { container } = render(
      <ReactFlowProvider>
        <HandleRenderComponent
          {...baseProps}
          left={true}
          showNode={false}
          minimizedHandleTop="40%"
        />
      </ReactFlowProvider>,
    );

    expect(
      screen.getByLabelText(
        "Input handle for Message on node ChatInput-abc123",
      ),
    ).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
