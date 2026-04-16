import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockCurrentFlowId: string | undefined = "flow-1";
let mockIsPreparingDeploy = false;
let mockChoiceDialogOpen = false;
let mockDeployModalOpen = false;
const mockHandleDeploy = jest.fn();
const mockSetChoiceDialogOpen = jest.fn();
const mockSetDeployModalOpen = jest.fn();

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (
    selector: (s: { featureFlags: Record<string, unknown> }) => unknown,
  ) => selector({ featureFlags: { wxo_deployments: true } }),
}));

jest.mock("../deploy-choice-dialog/hooks/use-prepare-deploy", () => ({
  usePrepareDeploy: () => ({
    currentFlowId: mockCurrentFlowId,
    isPreparingDeploy: mockIsPreparingDeploy,
    choiceDialogOpen: mockChoiceDialogOpen,
    setChoiceDialogOpen: mockSetChoiceDialogOpen,
    deployModalOpen: mockDeployModalOpen,
    setDeployModalOpen: mockSetDeployModalOpen,
    providers: [],
    pendingSnapshotVersionId: "",
    initialVersionByFlow: new Map(),
    stepperInitialProvider: undefined,
    stepperInitialInstance: undefined,
    handleDeploy: mockHandleDeploy,
    handleChooseNew: jest.fn(),
    handleUpdateComplete: jest.fn(),
    resetChoiceState: jest.fn(),
  }),
}));

jest.mock(
  "@/pages/MainPage/pages/deploymentsPage/hooks/use-navigate-to-test",
  () => ({
    useNavigateToTest: () => jest.fn(),
  }),
);

jest.mock("../deploy-choice-dialog", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock(
  "@/pages/MainPage/pages/deploymentsPage/components/deployment-stepper-modal",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);

// Override global mock to forward className so animate-pulse can be tested
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className ?? ""} />
  ),
}));

import DeployButton from "../deploy-button";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  mockCurrentFlowId = "flow-1";
  mockIsPreparingDeploy = false;
  mockChoiceDialogOpen = false;
  mockDeployModalOpen = false;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DeployButton — rendering", () => {
  it("renders the deploy button with data-testid", () => {
    render(<DeployButton />);

    expect(screen.getByTestId("deploy-btn-flow")).toBeInTheDocument();
  });

  it("renders Deploy text label", () => {
    render(<DeployButton />);

    expect(screen.getByText("Deploy")).toBeInTheDocument();
  });

  it("renders the Rocket icon", () => {
    render(<DeployButton />);

    expect(screen.getByTestId("icon-Rocket")).toBeInTheDocument();
  });
});

describe("DeployButton — disabled states", () => {
  it("is enabled when currentFlowId is set and nothing is busy", () => {
    render(<DeployButton />);

    expect(screen.getByTestId("deploy-btn-flow")).not.toBeDisabled();
  });

  it("is disabled when currentFlowId is undefined", () => {
    mockCurrentFlowId = undefined;
    render(<DeployButton />);

    expect(screen.getByTestId("deploy-btn-flow")).toBeDisabled();
  });

  it("is disabled when isPreparingDeploy is true", () => {
    mockIsPreparingDeploy = true;
    render(<DeployButton />);

    expect(screen.getByTestId("deploy-btn-flow")).toBeDisabled();
  });

  it("is disabled when choiceDialogOpen is true", () => {
    mockChoiceDialogOpen = true;
    render(<DeployButton />);

    expect(screen.getByTestId("deploy-btn-flow")).toBeDisabled();
  });

  it("is disabled when deployModalOpen is true", () => {
    mockDeployModalOpen = true;
    render(<DeployButton />);

    expect(screen.getByTestId("deploy-btn-flow")).toBeDisabled();
  });
});

describe("DeployButton — click interaction", () => {
  it("calls handleDeploy when button is clicked", async () => {
    const user = userEvent.setup();
    render(<DeployButton />);

    await user.click(screen.getByTestId("deploy-btn-flow"));

    expect(mockHandleDeploy).toHaveBeenCalledTimes(1);
  });

  it("does not call handleDeploy when disabled with no currentFlowId", async () => {
    const user = userEvent.setup();
    mockCurrentFlowId = undefined;
    render(<DeployButton />);

    await user.click(screen.getByTestId("deploy-btn-flow"));

    expect(mockHandleDeploy).not.toHaveBeenCalled();
  });

  it("does not call handleDeploy when disabled while preparing", async () => {
    const user = userEvent.setup();
    mockIsPreparingDeploy = true;
    render(<DeployButton />);

    await user.click(screen.getByTestId("deploy-btn-flow"));

    expect(mockHandleDeploy).not.toHaveBeenCalled();
  });
});

describe("DeployButton — loading pulse", () => {
  it("applies animate-pulse to Rocket icon when isPreparingDeploy is true", () => {
    mockIsPreparingDeploy = true;
    render(<DeployButton />);

    expect(screen.getByTestId("icon-Rocket").className).toContain(
      "animate-pulse",
    );
  });

  it("does not apply animate-pulse when isPreparingDeploy is false", () => {
    mockIsPreparingDeploy = false;
    render(<DeployButton />);

    expect(screen.getByTestId("icon-Rocket").className).not.toContain(
      "animate-pulse",
    );
  });
});
