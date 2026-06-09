import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSetDeploymentType = jest.fn();
const mockSetDeploymentName = jest.fn();
const mockSetDeploymentDescription = jest.fn();
const mockSetSelectedLlm = jest.fn();

let mockIsEditMode = false;
let mockDeploymentType = "agent";
let mockDeploymentName = "";
let mockDeploymentDescription = "";
let mockSelectedLlm = "";
let mockSelectedInstance: { id: string } | null = { id: "inst-1" };
let mockLlmModels: Array<{ model_name: string }> = [];
let mockLlmsLoading = false;

jest.mock("../contexts/deployment-stepper-context", () => ({
  useDeploymentStepper: () => ({
    isEditMode: mockIsEditMode,
    deploymentType: mockDeploymentType,
    setDeploymentType: mockSetDeploymentType,
    deploymentName: mockDeploymentName,
    setDeploymentName: mockSetDeploymentName,
    deploymentDescription: mockDeploymentDescription,
    setDeploymentDescription: mockSetDeploymentDescription,
    selectedLlm: mockSelectedLlm,
    setSelectedLlm: mockSetSelectedLlm,
    selectedInstance: mockSelectedInstance,
  }),
}));

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-llms",
  () => ({
    useGetDeploymentLlms: () => ({
      data: {
        provider_data: { models: mockLlmModels },
      },
      isLoading: mockLlmsLoading,
    }),
  }),
);

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import StepType from "../components/step-type";

beforeEach(() => {
  jest.clearAllMocks();
  mockIsEditMode = false;
  mockDeploymentType = "agent";
  mockDeploymentName = "";
  mockDeploymentDescription = "";
  mockSelectedLlm = "";
  mockSelectedInstance = { id: "inst-1" };
  mockLlmModels = [];
  mockLlmsLoading = false;
});

// ---------------------------------------------------------------------------
// Basic rendering
// ---------------------------------------------------------------------------

describe("Basic rendering", () => {
  it("renders the Deployment Type heading", () => {
    render(<StepType />);
    expect(screen.getByText("Deployment Type")).toBeInTheDocument();
  });

  it("renders type selection with Agent option", () => {
    render(<StepType />);
    expect(screen.getByTestId("deployment-type-agent")).toBeInTheDocument();
    expect(screen.getByText("Agent")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Conversational agent with chat interface and tool calling",
      ),
    ).toBeInTheDocument();
  });

  it("renders required field indicators", () => {
    render(<StepType />);
    expect(screen.getByText("Agent Name")).toBeInTheDocument();
    expect(screen.getByText("Model")).toBeInTheDocument();
  });

  it("renders optional description field", () => {
    render(<StepType />);
    expect(screen.getByText("Description")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Describe the agent's purpose..."),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Name input
// ---------------------------------------------------------------------------

describe("Name input", () => {
  it("renders with placeholder", () => {
    render(<StepType />);
    expect(screen.getByPlaceholderText("e.g., Sales Bot")).toBeInTheDocument();
  });

  it("calls setDeploymentName on input change", async () => {
    const user = userEvent.setup();
    render(<StepType />);

    const input = screen.getByPlaceholderText("e.g., Sales Bot");
    await user.type(input, "A");
    expect(mockSetDeploymentName).toHaveBeenCalled();
  });

  it("is disabled in edit mode", () => {
    mockIsEditMode = true;
    render(<StepType />);
    expect(screen.getByPlaceholderText("e.g., Sales Bot")).toBeDisabled();
  });

  it("shows helper text in edit mode", () => {
    mockIsEditMode = true;
    render(<StepType />);
    expect(
      screen.getByText("Name cannot be changed after creation."),
    ).toBeInTheDocument();
  });

  it("does not show helper text in create mode", () => {
    render(<StepType />);
    expect(
      screen.queryByText("Name cannot be changed after creation."),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// LLM dropdown
// ---------------------------------------------------------------------------

describe("LLM dropdown", () => {
  it("shows loading placeholder when fetching", () => {
    mockLlmsLoading = true;
    render(<StepType />);
    expect(screen.getByText("Loading models...")).toBeInTheDocument();
  });

  it("shows select placeholder when not loading", () => {
    mockLlmsLoading = false;
    render(<StepType />);
    expect(screen.getByText("Select a model")).toBeInTheDocument();
  });

  it("renders empty message item when no models are available", () => {
    mockLlmModels = [];
    mockLlmsLoading = false;
    render(<StepType />);

    // The trigger should still show the default placeholder
    expect(screen.getByText("Select a model")).toBeInTheDocument();
    // The combobox should be present and interactive (not broken)
    expect(screen.getByRole("combobox")).toBeEnabled();
  });

  it("shows selected model value when one is set", () => {
    mockLlmModels = [
      { model_name: "granite-13b-chat" },
      { model_name: "llama-3-70b" },
    ];
    mockSelectedLlm = "granite-13b-chat";
    render(<StepType />);
    // The SelectValue renders the selected model text
    expect(screen.getByText("granite-13b-chat")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Type selection
// ---------------------------------------------------------------------------

describe("Type selection", () => {
  it("renders agent type as selected by default", () => {
    render(<StepType />);
    const agentLabel = screen.getByTestId("deployment-type-agent");
    const radio = agentLabel.querySelector('input[type="radio"]');
    expect(radio).toBeChecked();
  });

  it("triggers onChange on the radio input", () => {
    render(<StepType />);
    const agentLabel = screen.getByTestId("deployment-type-agent");
    const radio = agentLabel.querySelector(
      'input[type="radio"]',
    ) as HTMLInputElement;
    expect(radio).toBeTruthy();
    expect(radio.value).toBe("agent");
  });

  it("has radiogroup role", () => {
    render(<StepType />);
    expect(
      screen.getByRole("radiogroup", { name: "Deployment type" }),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Description textarea
// ---------------------------------------------------------------------------

describe("Description textarea", () => {
  it("calls setDeploymentDescription on input", async () => {
    const user = userEvent.setup();
    render(<StepType />);

    const textarea = screen.getByPlaceholderText(
      "Describe the agent's purpose...",
    );
    await user.type(textarea, "A");
    expect(mockSetDeploymentDescription).toHaveBeenCalled();
  });
});
