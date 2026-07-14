import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import InspectionPanelHeader from "../components/InspectionPanelHeader";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: function MockIconComponent({ name }: any) {
    return <span data-testid={`icon-${name}`}>{name}</span>;
  },
}));

const mockSetInspectionPanelVisible = jest.fn();
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({ setInspectionPanelVisible: mockSetInspectionPanelVisible }),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

const renderWithProviders = () =>
  render(
    <TooltipProvider>
      <InspectionPanelHeader />
    </TooltipProvider>,
  );

describe("InspectionPanelHeader", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the static title", () => {
    renderWithProviders();

    expect(screen.getByTestId("panel-title")).toHaveTextContent(
      "Component Parameters",
    );
  });

  it("renders the exact LE-1810 subtitle", () => {
    renderWithProviders();

    expect(screen.getByTestId("panel-subtitle")).toHaveTextContent(
      "Adjust component parameter visibility and define API inputs.",
    );
  });

  it("closes the panel via the store", async () => {
    const user = userEvent.setup();
    renderWithProviders();

    await user.click(screen.getByTestId("inspection-panel-close"));

    expect(mockSetInspectionPanelVisible).toHaveBeenCalledWith(false);
  });

  it("renders no field-editing or code affordances", () => {
    renderWithProviders();

    expect(screen.queryByTestId("edit-fields-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("code-button-modal")).not.toBeInTheDocument();
    expect(screen.queryByTestId("docs-button-modal")).not.toBeInTheDocument();
  });
});
