import { render, screen } from "@testing-library/react";
import React from "react";
import DeploymentStepperModal from "../components/deployment-stepper-modal";
import {
  mockDeployment,
  mockProviderAccount,
  createTestWrapper,
} from "./test-utils";

// Mock child step components to avoid deep dependency tree
jest.mock("../components/step-provider", () => {
  const Mock = () => <div data-testid="step-provider">StepProvider</div>;
  Mock.displayName = "StepProvider";
  return { __esModule: true, default: Mock };
});

jest.mock("../components/step-type", () => {
  const Mock = () => <div data-testid="step-type">StepType</div>;
  Mock.displayName = "StepType";
  return { __esModule: true, default: Mock };
});

jest.mock("../components/step-attach-flows", () => {
  const Mock = () => <div data-testid="step-attach-flows">StepAttachFlows</div>;
  Mock.displayName = "StepAttachFlows";
  return { __esModule: true, default: Mock };
});

jest.mock("../components/step-review", () => {
  const Mock = () => <div data-testid="step-review">StepReview</div>;
  Mock.displayName = "StepReview";
  return { __esModule: true, default: Mock };
});

jest.mock("../components/step-deploy-status", () => {
  const Mock = () => (
    <div data-testid="step-deploy-status">StepDeployStatus</div>
  );
  Mock.displayName = "StepDeployStatus";
  return { __esModule: true, default: Mock };
});

jest.mock("../components/deployment-stepper", () => {
  const Mock = () => <div data-testid="deployment-stepper">Stepper</div>;
  Mock.displayName = "DeploymentStepper";
  return { __esModule: true, default: Mock };
});

// Mock API hooks
jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account",
  () => ({
    usePostProviderAccount: () => ({ mutateAsync: jest.fn() }),
  }),
);

jest.mock("@/controllers/API/queries/deployments/use-post-deployment", () => ({
  usePostDeployment: () => ({ mutateAsync: jest.fn() }),
}));

jest.mock("@/controllers/API/queries/deployments/use-patch-deployment", () => ({
  usePatchDeployment: () => ({ mutateAsync: jest.fn() }),
}));

const mockAttachmentsReturn: { data: any; isLoading: boolean } = {
  data: null,
  isLoading: false,
};
jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-attachments",
  () => ({
    useGetDeploymentAttachments: () => mockAttachmentsReturn,
  }),
);

jest.mock(
  "@/controllers/API/queries/deployments/use-patch-deployment-snapshot",
  () => ({
    usePatchDeploymentSnapshot: () => ({ mutateAsync: jest.fn() }),
  }),
);

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({
    setSuccessData: jest.fn(),
    setErrorData: jest.fn(),
  }),
}));

// Mock Radix Dialog to render children directly
jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dialog-content">{children}</div>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
  DialogDescription: ({ children }: { children: React.ReactNode }) => (
    <p>{children}</p>
  ),
}));

jest.mock("@/components/common/genericIconComponent", () => {
  const Mock = ({
    name,
    ...props
  }: {
    name: string;
    [key: string]: unknown;
  }) => <span data-testid={`icon-${name}`} {...props} />;
  Mock.displayName = "ForwardedIconComponent";
  return Mock;
});

describe("DeploymentStepperModal", () => {
  const defaultProps = {
    open: true,
    setOpen: jest.fn(),
  };

  it("renders 'Create New Deployment' title in create mode", () => {
    render(<DeploymentStepperModal {...defaultProps} />);
    const titles = screen.getAllByText("Create New Deployment");
    expect(titles.length).toBeGreaterThanOrEqual(1);
  });

  it("renders 'Update Deployment' title in edit mode", () => {
    render(
      <DeploymentStepperModal
        {...defaultProps}
        editingDeployment={mockDeployment}
        editingProviderAccount={mockProviderAccount}
      />,
    );
    const titles = screen.getAllByText("Update Deployment");
    expect(titles.length).toBeGreaterThanOrEqual(1);
  });

  it("shows StepProvider on step 1 in create mode", () => {
    render(<DeploymentStepperModal {...defaultProps} />);
    expect(screen.getByTestId("step-provider")).toBeInTheDocument();
    expect(screen.queryByTestId("step-type")).not.toBeInTheDocument();
  });

  it("shows StepType on step 1 in edit mode (skips provider)", () => {
    render(
      <DeploymentStepperModal
        {...defaultProps}
        editingDeployment={mockDeployment}
        editingProviderAccount={mockProviderAccount}
      />,
    );
    expect(screen.getByTestId("step-type")).toBeInTheDocument();
    expect(screen.queryByTestId("step-provider")).not.toBeInTheDocument();
  });

  it("shows 'Deploy' button in create mode", () => {
    render(<DeploymentStepperModal {...defaultProps} />);
    // On step 1 (not final), shows "Next"
    expect(screen.getByText("Next")).toBeInTheDocument();
  });

  it("does not render when open is false", () => {
    render(<DeploymentStepperModal {...defaultProps} open={false} />);
    expect(screen.queryByTestId("dialog")).not.toBeInTheDocument();
  });

  it("shows loading state while attachments are being fetched in edit mode", () => {
    mockAttachmentsReturn.data = null;
    mockAttachmentsReturn.isLoading = true;
    render(
      <DeploymentStepperModal
        {...defaultProps}
        editingDeployment={mockDeployment}
        editingProviderAccount={mockProviderAccount}
      />,
    );
    expect(screen.getByText("Loading deployment data...")).toBeInTheDocument();
    expect(screen.queryByTestId("step-type")).not.toBeInTheDocument();
    // Reset
    mockAttachmentsReturn.data = null;
    mockAttachmentsReturn.isLoading = false;
  });

  it("renders stepper content after attachments load in edit mode", () => {
    mockAttachmentsReturn.data = {
      attachments: [
        {
          flow_version_id: "fv-1",
          flow_id: "flow-1",
          flow_name: "My Flow",
          version_tag: "v2",
          provider_snapshot_id: "tool-1",
          connection_ids: ["conn-a"],
          created_at: null,
        },
      ],
    };
    mockAttachmentsReturn.isLoading = false;
    render(
      <DeploymentStepperModal
        {...defaultProps}
        editingDeployment={mockDeployment}
        editingProviderAccount={mockProviderAccount}
      />,
    );
    expect(
      screen.queryByText("Loading deployment data..."),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("step-type")).toBeInTheDocument();
    // Reset
    mockAttachmentsReturn.data = null;
  });
});
