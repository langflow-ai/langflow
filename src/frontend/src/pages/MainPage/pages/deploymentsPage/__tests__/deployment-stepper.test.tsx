import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";

let mockCurrentStep = 1;
let mockIsEditMode = false;

jest.mock("../contexts/deployment-stepper-context", () => ({
  useDeploymentStepper: () => ({
    currentStep: mockCurrentStep,
    isEditMode: mockIsEditMode,
  }),
}));

import DeploymentStepper from "../components/deployment-stepper";

beforeEach(() => {
  mockCurrentStep = 1;
  mockIsEditMode = false;
});

describe("Accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(<DeploymentStepper />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("exposes the steps as a list with the current step marked via aria-current", () => {
    mockCurrentStep = 2;
    render(<DeploymentStepper />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(4);
    expect(items[1]).toHaveAttribute("aria-current", "step");
    expect(items[0]).not.toHaveAttribute("aria-current");
    expect(items[2]).not.toHaveAttribute("aria-current");
  });

  it("names each step by its label, not just a decorative number", () => {
    render(<DeploymentStepper />);

    expect(screen.getByText("Provider")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Flows")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("shows edit-mode steps (3 steps, no Provider) with correct current step", () => {
    mockIsEditMode = true;
    mockCurrentStep = 1;
    render(<DeploymentStepper />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(screen.queryByText("Provider")).not.toBeInTheDocument();
    expect(items[0]).toHaveAttribute("aria-current", "step");
  });
});
