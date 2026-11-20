import { fireEvent, render, screen } from "@testing-library/react";
import { mockGenericIconComponent } from "@/components/core/parameterRenderComponent/components/__tests__/a11y-mock-helpers";
import ToolsComponent from "@/components/core/parameterRenderComponent/components/ToolsComponent";
import useFlowStore from "@/stores/flowStore";
import { FlowEditCarousel } from "../assistant-flow-edit-card";

jest.mock("@/modals/toolsModal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/common/genericIconComponent", () =>
  mockGenericIconComponent(),
);

const HELPERS = [
  ["Shipping", "Find the shipping status and delivery estimate for an order."],
  ["Billing", "Answer billing questions and explain charges on an invoice."],
  ["Returns", "Explain return eligibility and help start an exchange."],
  ["Inventory", "Check current stock and explain availability by product."],
  ["Warranty", "Explain warranty coverage and claim requirements."],
] as const;

function toolRow(name: string, description: string) {
  return {
    name: `${name}-helper_tool`,
    description,
    tags: [`${name}-helper_tool`],
    status: true,
    approval_actions: [] as string[],
    display_name: "message",
    display_description: "Executes another flow.",
    readonly: false,
  };
}

function runFlowNode(index: number, name: string) {
  const id = `RunFlow-Rep0${index + 1}`;
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: index * 120 },
    data: {
      id,
      type: "RunFlow",
      node: {
        display_name: "Run Flow",
        description: "Executes another flow.",
        template: {
          tools_metadata: {
            type: "tools",
            show: true,
            value: [
              toolRow(
                name,
                `Tool designed to execute the flow '${name} helper'.`,
              ),
            ],
          },
        },
        outputs: [],
      },
    },
  };
}

function descriptionEdit(index: number, name: string, description: string) {
  const id = `RunFlow-Rep0${index + 1}`;
  const row = toolRow(name, description);
  const serialized = JSON.stringify([row]);
  return {
    id: `edit-${index + 1}`,
    type: "edit_field" as const,
    description: `Set tools_metadata to "${description}" on RunFlow`,
    component_id: id,
    component_type: "RunFlow",
    field: "tools_metadata",
    old_value: [
      toolRow(name, `Tool designed to execute the flow '${name} helper'.`),
    ],
    new_value: serialized,
    patch: [
      {
        op: "replace",
        path: `/data/nodes/${index}/data/node/template/tools_metadata/value`,
        value: serialized,
      },
    ],
    status: "pending" as const,
  };
}

function ToolBadges() {
  const nodes = useFlowStore((state) => state.nodes);
  return (
    <>
      {nodes.map((node) => {
        const value = (
          node.data as {
            node?: { template?: { tools_metadata?: { value?: unknown } } };
          }
        ).node?.template?.tools_metadata?.value;
        return (
          <ToolsComponent
            key={node.id}
            id={node.id}
            value={value as never}
            handleOnNewValue={jest.fn()}
            description=""
            title="Tools"
            editNode={false}
            disabled={false}
          />
        );
      })}
    </>
  );
}

describe("FlowEditCarousel — five Run Flow tool descriptions", () => {
  const nodes = HELPERS.map(([name], index) => runFlowNode(index, name));

  beforeEach(() => {
    useFlowStore.setState({
      nodes: nodes as never,
      edges: [],
      currentFlow: {
        data: { nodes, edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
      } as never,
      autoSaveFlow: undefined,
    });
  });

  it("should_keep_tool_rows_as_a_list_after_accepting_five_description_edits", () => {
    const actions = HELPERS.map(([name, description], index) =>
      descriptionEdit(index, name, description),
    );
    render(
      <>
        <FlowEditCarousel
          actions={actions as never}
          onUpdateAction={jest.fn()}
        />
        <ToolBadges />
      </>,
    );

    fireEvent.click(screen.getByRole("button", { name: /accept all/i }));

    HELPERS.forEach(([name, description], index) => {
      expect(
        screen.getByText(`${name}-helper_tool`.toUpperCase()),
      ).toBeInTheDocument();
      const node = useFlowStore
        .getState()
        .nodes.find((candidate) => candidate.id === `RunFlow-Rep0${index + 1}`);
      const value = (
        node?.data as {
          node?: {
            template?: {
              tools_metadata?: { value?: { description?: string }[] };
            };
          };
        }
      )?.node?.template?.tools_metadata?.value;
      expect(Array.isArray(value)).toBe(true);
      expect(value?.[0]?.description).toBe(description);
    });
  });
});
