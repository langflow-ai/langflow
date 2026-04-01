import { render, screen } from "@testing-library/react";
import React from "react";
import DeploymentStepper from "../components/deployment-stepper";
import { DeploymentStepperProvider } from "../contexts/deployment-stepper-context";
import { mockDeployment, mockProviderAccount } from "./test-utils";

// Minimal mocks
jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account",
  () => ({
    usePostProviderAccount: jest.fn(),
  }),
);
jest.mock("@/controllers/API/queries/deployments/use-post-deployment", () => ({
  usePostDeployment: jest.fn(),
}));
jest.mock("@/controllers/API/queries/deployments/use-patch-deployment", () => ({
  usePatchDeployment: jest.fn(),
}));

function renderStepper(
  initialState?: Parameters<
    typeof DeploymentStepperProvider
  >[0]["initialState"],
) {
  return render(
    <DeploymentStepperProvider initialState={initialState}>
      <DeploymentStepper />
    </DeploymentStepperProvider>,
  );
}

describe("DeploymentStepper – create mode", () => {
  it("renders 4 steps: Provider, Type, Attach Flows, Review", () => {
    renderStepper();
    expect(screen.getByText("Provider")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Attach Flows")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("renders step numbers 1–4", () => {
    renderStepper();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });
});

describe("DeploymentStepper – edit mode", () => {
  it("renders 3 steps: Type, Attach Flows, Review (no Provider)", () => {
    renderStepper({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    expect(screen.queryByText("Provider")).not.toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Attach Flows")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("renders step numbers 1–3", () => {
    renderStepper({
      editingDeployment: mockDeployment,
      editingProviderAccount: mockProviderAccount,
    });
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.queryByText("4")).not.toBeInTheDocument();
  });
});
