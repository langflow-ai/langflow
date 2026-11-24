import { act, render, screen } from "@testing-library/react";
import type { CustomResourceAccessLabelProps } from "@/customization/components/custom-resource-access-label";
import type { FlowType } from "@/types/flow";
import ListComponent from "../index";

let mockUseLabelSeam = false;

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: undefined }),
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));
jest.mock("@/hooks/flows/use-delete-flow", () => ({
  __esModule: true,
  default: () => ({ deleteFlow: jest.fn() }),
}));
jest.mock("@/modals/deleteConfirmationModal", () => () => null);
jest.mock("@/modals/exportModal", () => () => null);
jest.mock("@/modals/flowSettingsModal", () => () => null);
jest.mock("@/pages/MainPage/components/dropdown", () => () => null);
jest.mock("@/customization/components/custom-resource-access-label", () => {
  const actual = jest.requireActual(
    "@/customization/components/custom-resource-access-label",
  );
  return {
    __esModule: true,
    default: (props: CustomResourceAccessLabelProps) =>
      mockUseLabelSeam ? (
        <span
          data-testid="access-label"
          data-resource-type={props.resourceType}
          data-resource-id={props.resourceId}
          data-owned={String(props.isOwned)}
        >
          Shared by priya (Can edit)
        </span>
      ) : (
        actual.default(props)
      ),
  };
});

const LONG_NAME = `flow_${"x".repeat(300)}`;

const makeFlow = (overrides: Partial<FlowType> = {}) =>
  ({
    id: "flow-1",
    name: "Starter Project",
    description: "",
    is_component: false,
    updated_at: new Date().toISOString(),
    ...overrides,
  }) as FlowType;

const renderCard = async (flow: FlowType, isOwned: boolean) => {
  const view = render(
    <ListComponent
      flowData={flow}
      selected={false}
      setSelected={jest.fn()}
      shiftPressed={false}
      isOwned={isOwned}
    />,
  );
  await act(async () => {});
  return view;
};

// The column that stacks the name row and anything rendered under it.
const nameColumn = (flowId: string) =>
  screen.getByTestId(`flow-name-${flowId}`).closest(".flex-col") as HTMLElement;

describe("ListComponent access label", () => {
  beforeEach(() => {
    mockUseLabelSeam = false;
  });

  it("should_leave_the_name_column_with_only_the_name_row_when_the_label_is_the_default", async () => {
    await renderCard(makeFlow(), false);

    expect(nameColumn("flow-1").children).toHaveLength(1);
    expect(screen.queryByTestId("access-label")).not.toBeInTheDocument();
  });

  it("should_render_the_label_under_the_name_with_flow_props_when_the_seam_renders", async () => {
    mockUseLabelSeam = true;
    await renderCard(makeFlow({ id: "flow-9" }), false);

    const label = screen.getByTestId("access-label");
    const column = nameColumn("flow-9");
    expect(column.lastElementChild).toBe(label);
    expect(column.children).toHaveLength(2);
    expect(label).toHaveAttribute("data-resource-type", "flow");
    expect(label).toHaveAttribute("data-resource-id", "flow-9");
    expect(label).toHaveAttribute("data-owned", "false");
  });

  it("should_pass_isOwned_true_through_to_the_label", async () => {
    mockUseLabelSeam = true;
    await renderCard(makeFlow(), true);

    expect(screen.getByTestId("access-label")).toHaveAttribute(
      "data-owned",
      "true",
    );
  });

  it("should_keep_a_long_unbroken_name_truncated_beside_the_label", async () => {
    mockUseLabelSeam = true;
    await renderCard(makeFlow({ name: LONG_NAME }), false);

    expect(screen.getByTestId("flow-name-flow-1")).toHaveClass("truncate");
    expect(nameColumn("flow-1")).toHaveClass("min-w-0");
  });
});
