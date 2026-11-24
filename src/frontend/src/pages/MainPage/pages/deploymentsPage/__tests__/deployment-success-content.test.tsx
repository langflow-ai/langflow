import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DeploymentSuccessContent from "../components/deployment-success-content";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

describe("DeploymentSuccessContent", () => {
  it("renders success copy and provider link", () => {
    render(
      <DeploymentSuccessContent
        deploymentName="My Agent"
        providerName="watsonx Orchestrate"
        providerUrl="https://www.ibm.com/products/watsonx-orchestrate"
        showTestButton={true}
        onTest={jest.fn()}
      />,
    );

    expect(screen.getByText("Deployment successful")).toBeInTheDocument();
    expect(
      screen.getByText("Deployed to watsonx Orchestrate as draft"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /watsonx Orchestrate/i }),
    ).toHaveAttribute(
      "href",
      "https://www.ibm.com/products/watsonx-orchestrate",
    );
  });

  it("shows test button and calls handler", async () => {
    const user = userEvent.setup();
    const onTest = jest.fn();

    render(
      <DeploymentSuccessContent
        deploymentName="My Agent"
        providerName="watsonx Orchestrate"
        providerUrl="https://www.ibm.com/products/watsonx-orchestrate"
        showTestButton={true}
        onTest={onTest}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Test Deployment" }));

    expect(onTest).toHaveBeenCalled();
  });

  it("hides test button without deployment name", () => {
    render(
      <DeploymentSuccessContent
        providerName="watsonx Orchestrate"
        providerUrl="https://www.ibm.com/products/watsonx-orchestrate"
        showTestButton={true}
        onTest={jest.fn()}
      />,
    );

    expect(
      screen.queryByRole("button", { name: "Test Deployment" }),
    ).not.toBeInTheDocument();
  });

  it("hides test button when showTestButton is false", () => {
    render(
      <DeploymentSuccessContent
        deploymentName="My Agent"
        providerName="watsonx Orchestrate"
        providerUrl="https://www.ibm.com/products/watsonx-orchestrate"
        showTestButton={false}
        onTest={jest.fn()}
      />,
    );

    expect(
      screen.queryByRole("button", { name: "Test Deployment" }),
    ).not.toBeInTheDocument();
  });
});
