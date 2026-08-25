import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import InspectionPanelHeader from "../components/InspectionPanelHeader";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: function MockIconComponent({ name }: { name: string }) {
    return <span data-testid={`icon-${name}`}>{name}</span>;
  },
}));

const mockSetInspectionPanelVisible = jest.fn();
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setInspectionPanelVisible: mockSetInspectionPanelVisible }),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: string[]) => classes.filter(Boolean).join(" "),
}));

let mockTweaksPolicy = "permissive";
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: unknown) => unknown) =>
    selector({ tweaksPolicy: mockTweaksPolicy }),
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
    mockTweaksPolicy = "permissive";
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

  // The per-field API toggle is only enforced under "declared". A panel that
  // stays silent about the active policy lets the toggle read as a guarantee
  // the default deployment does not give.
  it("states that the default policy does not restrict API inputs per field", () => {
    renderWithProviders();

    expect(
      screen.getByTestId("panel-tweaks-policy-permissive"),
    ).toHaveTextContent(
      "Tweaks policy: permissive. The API can set any unprotected field, marked or not.",
    );
  });

  it("states that the toggle is enforced under the declared policy", () => {
    mockTweaksPolicy = "declared";
    renderWithProviders();

    expect(
      screen.getByTestId("panel-tweaks-policy-declared"),
    ).toHaveTextContent(
      "Tweaks policy: declared. Once one field is marked, the API can set only the marked fields.",
    );
  });

  it("states that an off deployment refuses every API input", () => {
    mockTweaksPolicy = "off";
    renderWithProviders();

    expect(screen.getByTestId("panel-tweaks-policy-off")).toHaveTextContent(
      "Tweaks policy: off. This deployment refuses every API input.",
    );
  });

  it("renders no field-editing or code affordances", () => {
    renderWithProviders();

    expect(screen.queryByTestId("edit-fields-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("code-button-modal")).not.toBeInTheDocument();
    expect(screen.queryByTestId("docs-button-modal")).not.toBeInTheDocument();
  });
});
