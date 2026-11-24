import { render, screen } from "@testing-library/react";
import type { ForwardedRef } from "react";
import type { NodeDataType } from "@/types/flow";
import { axe } from "@/utils/a11y-test";
import EditNodeModal from "../index";

// AG Grid measures real layout and is not renderable in jsdom. This is the
// same stub the TableComponent a11y test uses; the grid's own semantics are
// covered there, so here it stands in as an already-audited child while the
// modal shell is what gets audited.
const mockApi = {
  applyColumnState: jest.fn(),
  getColumnDefs: jest.fn(() => []),
  getColumnState: jest.fn(() => []),
  getColumns: jest.fn(() => []),
  getSelectedRows: jest.fn(() => []),
  hideOverlay: jest.fn(),
  isDestroyed: jest.fn(() => false),
  setGridAriaProperty: jest.fn(),
  setGridOption: jest.fn(),
  sizeColumnsToFit: jest.fn(),
};

jest.mock("ag-grid-react", () => {
  const React = require("react");
  type MockGridReadyParams = {
    api: typeof mockApi;
    columnApi: { getAllGridColumns: jest.Mock };
  };
  type MockAgGridProps = {
    onGridReady?: (params: MockGridReadyParams) => void;
  };

  return {
    AgGridReact: React.forwardRef(
      (props: MockAgGridProps, ref: ForwardedRef<{ api: typeof mockApi }>) => {
        React.useImperativeHandle(ref, () => ({ api: mockApi }));
        React.useEffect(() => {
          props.onGridReady?.({
            api: mockApi,
            columnApi: { getAllGridColumns: jest.fn(() => []) },
          });
        }, [props.onGridReady]);

        return (
          <div aria-label="Node parameters" role="treegrid">
            <div role="row">
              <div role="gridcell">Model name</div>
            </div>
          </div>
        );
      },
    ),
  };
});

// nanoid ships browser ESM that jest does not transform; the table's key-pair
// cell reaches it transitively.
jest.mock("nanoid", () => ({ nanoid: () => "a11y-test-id" }));

const nodeData = {
  id: "OpenAIModel-a11y",
  type: "OpenAIModel",
  node: {
    display_name: "OpenAI",
    description: "Generates text with an OpenAI model.",
    template: {
      model_name: {
        type: "str",
        name: "model_name",
        display_name: "Model Name",
        value: "gpt-4",
        advanced: false,
        show: true,
      },
    },
  },
} as unknown as NodeDataType;

const renderModal = () =>
  render(<EditNodeModal open setOpen={jest.fn()} data={nodeData} />);

describe("EditNodeModal accessibility", () => {
  it("should_have_no_axe_violations_when_open", async () => {
    renderModal();

    // BaseModal portals its content to document.body, outside the render
    // container.
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_expose_dialog_role_named_after_the_node", () => {
    renderModal();

    // The node display name is the only thing distinguishing one edit dialog
    // from another, so it must be the accessible name (WCAG 2.4.6 / 4.1.2).
    expect(screen.getByRole("dialog", { name: /OpenAI/ })).toBeInTheDocument();
    expect(screen.getByTestId("node-modal-title")).toHaveTextContent("OpenAI");
  });

  it("should_use_the_node_description_as_the_dialog_description", () => {
    renderModal();

    expect(screen.getByRole("dialog")).toHaveAccessibleDescription(
      "Generates text with an OpenAI model.",
    );
    // A real description is present, so BaseModal must not inject the empty
    // visually-hidden fallback.
    expect(screen.queryByText("Dialog")).not.toBeInTheDocument();
  });

  it("should_expose_the_close_action_as_a_named_button", () => {
    renderModal();

    // Two controls close this dialog: BaseModal's built-in X and the footer
    // button. Both must carry a name — the X is icon-only, so an unnamed one
    // would be invisible to screen readers (WCAG 4.1.2).
    expect(screen.getByTestId("edit-button-close")).toHaveAccessibleName(
      "Close",
    );
    expect(screen.getAllByRole("button", { name: "Close" })).toHaveLength(2);
  });

  it("should_render_the_parameter_grid_inside_the_dialog", () => {
    renderModal();

    const dialog = screen.getByRole("dialog");
    const grid = screen.getByRole("treegrid", { name: "Node parameters" });
    expect(dialog).toContainElement(grid);
  });
});
