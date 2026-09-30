import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DeploymentStepperFooter from "../components/deployment-stepper-footer";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

describe("DeploymentStepperFooter", () => {
  it("shows done state controls when deployed", () => {
    render(
      <DeploymentStepperFooter
        canGoNext={true}
        currentStep={4}
        isCreatingAccount={false}
        isDeployed={true}
        isDeploying={false}
        isInDeployPhase={true}
        isFinalStep={true}
        minStep={1}
        actionIcon="Rocket"
        actionLabel="Deploy"
        progressLabel="Deploying..."
        onBack={jest.fn()}
        onCancel={jest.fn()}
        onClose={jest.fn()}
        onPrimaryAction={jest.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Done" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancel" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Back" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("deployment-stepper-next"),
    ).not.toBeInTheDocument();
  });

  it("calls onClose from done button", async () => {
    const user = userEvent.setup();
    const onClose = jest.fn();

    render(
      <DeploymentStepperFooter
        canGoNext={true}
        currentStep={4}
        isCreatingAccount={false}
        isDeployed={true}
        isDeploying={false}
        isInDeployPhase={true}
        isFinalStep={true}
        minStep={1}
        actionIcon="Rocket"
        actionLabel="Deploy"
        progressLabel="Deploying..."
        onBack={jest.fn()}
        onCancel={jest.fn()}
        onClose={onClose}
        onPrimaryAction={jest.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Done" }));

    expect(onClose).toHaveBeenCalled();
  });
});
