import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import DeploymentsTable from "../components/deployments-table";
import { mockDeployment } from "./test-utils";

jest.mock("@/components/common/genericIconComponent", () => {
  const Mock = ({ name, ...props }: { name: string; [key: string]: unknown }) => (
    <span data-testid={`icon-${name}`} {...props} />
  );
  Mock.displayName = "ForwardedIconComponent";
  return Mock;
});

jest.mock("@/components/ui/loading", () => {
  const Mock = () => <span data-testid="loading" />;
  Mock.displayName = "Loading";
  return { __esModule: true, default: Mock };
});

describe("DeploymentsTable", () => {
  const defaultProps = {
    deployments: [mockDeployment],
    providerName: "watsonx Orchestrate",
    onTestDeployment: jest.fn(),
    onUpdateDeployment: jest.fn(),
    onDeleteDeployment: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders deployment rows", () => {
    render(<DeploymentsTable {...defaultProps} />);
    expect(screen.getByText("My Agent")).toBeInTheDocument();
    expect(screen.getByText("A test agent")).toBeInTheDocument();
    expect(screen.getByText("watsonx Orchestrate")).toBeInTheDocument();
  });

  it("calls onUpdateDeployment when Update menu item is clicked", async () => {
    const user = userEvent.setup();
    render(<DeploymentsTable {...defaultProps} />);

    // Open the actions dropdown
    const actionsBtn = screen.getByTestId(`actions-deployment-${mockDeployment.id}`);
    await user.click(actionsBtn);

    // Click Update
    const updateItem = screen.getByText("Update");
    await user.click(updateItem);

    expect(defaultProps.onUpdateDeployment).toHaveBeenCalledWith(mockDeployment);
  });

  it("calls onDeleteDeployment when Delete menu item is clicked", async () => {
    const user = userEvent.setup();
    render(<DeploymentsTable {...defaultProps} />);

    const actionsBtn = screen.getByTestId(`actions-deployment-${mockDeployment.id}`);
    await user.click(actionsBtn);

    const deleteItem = screen.getByText("Delete");
    await user.click(deleteItem);

    expect(defaultProps.onDeleteDeployment).toHaveBeenCalledWith(mockDeployment);
  });

  it("calls onTestDeployment when Play button is clicked", async () => {
    const user = userEvent.setup();
    render(<DeploymentsTable {...defaultProps} />);

    const testBtn = screen.getByTestId(`test-deployment-${mockDeployment.id}`);
    await user.click(testBtn);

    expect(defaultProps.onTestDeployment).toHaveBeenCalledWith(mockDeployment);
  });

  it("shows loading state when deployment is being deleted", () => {
    render(
      <DeploymentsTable
        {...defaultProps}
        deletingId={mockDeployment.id}
      />,
    );
    expect(screen.getByTestId("loading")).toBeInTheDocument();
  });

  it("does not crash when onUpdateDeployment is not provided", async () => {
    const user = userEvent.setup();
    const { onUpdateDeployment, ...propsWithout } = defaultProps;
    render(<DeploymentsTable {...propsWithout} />);

    const actionsBtn = screen.getByTestId(`actions-deployment-${mockDeployment.id}`);
    await user.click(actionsBtn);

    const updateItem = screen.getByText("Update");
    // Should not throw
    await user.click(updateItem);
  });
});
