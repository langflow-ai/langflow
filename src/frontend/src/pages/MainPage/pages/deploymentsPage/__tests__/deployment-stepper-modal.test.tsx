import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Deployment, ProviderAccount } from "../types";

// ---------------------------------------------------------------------------
// Mocks — API hooks
// ---------------------------------------------------------------------------

let mockAttachmentsData: {
  flow_versions: Array<{
    id: string;
    flow_id: string;
    flow_name: string | null;
    version_number: number;
    attached_at: string | null;
    provider_snapshot_id: string | null;
    tool_name: string | null;
    provider_data: { app_ids?: string[] } | null;
  }>;
} | null = null;
let mockIsLoadingAttachments = false;

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-attachments",
  () => ({
    useGetDeploymentAttachments: () => ({
      data: mockAttachmentsData,
      isFetching: mockIsLoadingAttachments,
      isLoading: mockIsLoadingAttachments,
    }),
  }),
);

let mockDeploymentDetail: Deployment | null = null;
let mockIsLoadingDetail = false;

jest.mock("@/controllers/API/queries/deployments/use-get-deployment", () => ({
  useGetDeployment: () => ({
    data: mockDeploymentDetail,
    isFetching: mockIsLoadingDetail,
    isLoading: mockIsLoadingDetail,
  }),
}));

const mockCreateProviderAccount = jest.fn();
jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account",
  () => ({
    usePostProviderAccount: () => ({
      mutateAsync: mockCreateProviderAccount,
    }),
  }),
);

const mockCreateDeployment = jest.fn();
jest.mock("@/controllers/API/queries/deployments/use-post-deployment", () => ({
  usePostDeployment: () => ({
    mutateAsync: mockCreateDeployment,
  }),
}));

const mockUpdateDeployment = jest.fn();
jest.mock("@/controllers/API/queries/deployments/use-patch-deployment", () => ({
  usePatchDeployment: () => ({
    mutateAsync: mockUpdateDeployment,
  }),
}));

jest.mock("../hooks/use-error-alert", () => ({
  useErrorAlert: () => jest.fn(),
}));

// ---------------------------------------------------------------------------
// Mocks — stepper context internals (the modal provides the context)
//
// We need to mock the child step components to keep this test focused on
// the modal's own behavior (step navigation, deploy flow, edit mode loading).
// ---------------------------------------------------------------------------

jest.mock("../components/step-provider", () =>
  jest.fn(() => <div data-testid="step-provider">StepProvider</div>),
);
jest.mock("../components/step-type", () =>
  jest.fn(() => <div data-testid="step-type">StepType</div>),
);
jest.mock("../components/step-attach-flows", () =>
  jest.fn(() => <div data-testid="step-attach-flows">StepAttachFlows</div>),
);
jest.mock("../components/step-review", () =>
  jest.fn(() => <div data-testid="step-review">StepReview</div>),
);
jest.mock("../components/step-deploy-status", () =>
  jest.fn(({ phase }: { phase: string }) => (
    <div data-testid="step-deploy-status">{phase}</div>
  )),
);

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

jest.mock("@/components/ui/loading", () =>
  jest.fn(() => <span data-testid="loading-spinner" />),
);

// Mock hooks that the context depends on internally
jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts",
  () => ({
    useGetProviderAccounts: () => ({ data: undefined }),
  }),
);

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-configs",
  () => ({
    useGetDeploymentConfigs: () => ({ data: undefined }),
  }),
);

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-llms",
  () => ({
    useGetDeploymentLlms: () => ({ data: undefined, isLoading: false }),
  }),
);

jest.mock(
  "@/controllers/API/queries/flows/use-get-refresh-flows-query",
  () => ({
    useGetRefreshFlowsQuery: () => ({ data: [] }),
  }),
);

jest.mock(
  "@/controllers/API/queries/flow-version/use-get-flow-versions",
  () => ({
    useGetFlowVersions: () => ({ data: null, isLoading: false }),
  }),
);

jest.mock(
  "@/controllers/API/queries/variables/use-post-detect-env-vars",
  () => ({
    usePostDetectEnvVars: () => ({ mutateAsync: jest.fn() }),
  }),
);

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({ data: [] }),
}));

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: "folder-1" }),
}));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: () => "folder-1",
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

import DeploymentStepperModal from "../components/deployment-stepper-modal";

const makeDeployment = (overrides: Partial<Deployment> = {}): Deployment => ({
  id: "dep-1",
  name: "My Agent",
  description: "A sales agent",
  type: "agent",
  created_at: "2025-05-01T00:00:00Z",
  updated_at: "2025-06-10T00:00:00Z",
  provider_data: { llm: "granite-13b-chat" },
  resource_key: "rk-1",
  attached_count: 2,
  matched_attachments: null,
  provider_account_id: "prov-1",
  ...overrides,
});

const makeInstance = (
  overrides: Partial<ProviderAccount> = {},
): ProviderAccount => ({
  id: "inst-1",
  name: "Prod Instance",
  provider_tenant_id: "tenant-1",
  provider_key: "watsonx-orchestrate",
  provider_url: "https://api.example.com",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
  ...overrides,
});

function renderModal(
  overrides: Partial<Parameters<typeof DeploymentStepperModal>[0]> = {},
) {
  const setOpen = jest.fn();
  const result = render(
    <TooltipProvider>
      <DeploymentStepperModal open={true} setOpen={setOpen} {...overrides} />
    </TooltipProvider>,
  );
  return { setOpen, ...result };
}

beforeEach(() => {
  jest.clearAllMocks();
  mockAttachmentsData = null;
  mockIsLoadingAttachments = false;
  mockDeploymentDetail = null;
  mockIsLoadingDetail = false;
});

// ---------------------------------------------------------------------------
// Create mode — step navigation
// ---------------------------------------------------------------------------

describe("Create mode — step navigation", () => {
  it("renders Create New Deployment title", () => {
    renderModal();
    expect(screen.getAllByText("Create New Deployment")[0]).toBeInTheDocument();
  });

  it("starts on step 1 — StepProvider", () => {
    renderModal();
    expect(screen.getByTestId("step-provider")).toBeInTheDocument();
  });

  it("shows Cancel and Next buttons", () => {
    renderModal();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    // Next button has data-testid
    expect(screen.getByTestId("deployment-stepper-next")).toBeInTheDocument();
  });

  it("shows Back button disabled on first step", () => {
    renderModal();
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
  });

  it("skips to step 2 when initialProvider and initialInstance are provided", () => {
    renderModal({
      initialProvider: {
        id: "watsonx",
        type: "watsonx",
        name: "watsonx Orchestrate",
        icon: "Bot",
      },
      initialInstance: makeInstance(),
    });
    expect(screen.getByTestId("step-type")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Edit mode — loading & pre-population
// ---------------------------------------------------------------------------

describe("Edit mode — loading", () => {
  it("shows loading text when fetching edit data", () => {
    mockIsLoadingAttachments = true;
    mockIsLoadingDetail = true;
    renderModal({ editingDeployment: makeDeployment() });
    expect(screen.getByText("Loading deployment data...")).toBeInTheDocument();
  });

  it("renders Update Deployment title in edit mode once loaded", () => {
    mockAttachmentsData = { flow_versions: [] };
    mockDeploymentDetail = makeDeployment();
    renderModal({ editingDeployment: makeDeployment() });
    expect(screen.getAllByText("Update Deployment")[0]).toBeInTheDocument();
  });

  it("starts on step-type in edit mode (skips provider step)", () => {
    mockAttachmentsData = { flow_versions: [] };
    mockDeploymentDetail = makeDeployment();
    renderModal({ editingDeployment: makeDeployment() });
    expect(screen.getByTestId("step-type")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Edit mode — initial state from attachments
// ---------------------------------------------------------------------------

describe("Edit mode — initial state from attachments", () => {
  beforeEach(() => {
    mockDeploymentDetail = makeDeployment();
    mockAttachmentsData = {
      flow_versions: [
        {
          id: "fv-1",
          flow_id: "flow-1",
          flow_name: "Sales Flow",
          version_number: 2,
          attached_at: "2025-06-01T00:00:00Z",
          provider_snapshot_id: "snap-1",
          tool_name: "custom_sales_tool",
          provider_data: { app_ids: ["cfg-1"] },
        },
      ],
    };
  });

  it("renders without crashing with attachment data", () => {
    renderModal({ editingDeployment: makeDeployment() });
    expect(screen.getAllByText("Update Deployment")[0]).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Modal close prevention
// ---------------------------------------------------------------------------

describe("Modal close prevention during deploy", () => {
  it("renders the Cancel button", () => {
    renderModal();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("calls setOpen(false) when Cancel is clicked in idle state", async () => {
    const user = userEvent.setup();
    const { setOpen } = renderModal();

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(setOpen).toHaveBeenCalledWith(false);
  });
});

// ---------------------------------------------------------------------------
// Step labels
// ---------------------------------------------------------------------------

describe("Step labels", () => {
  it("shows all 4 step labels in create mode", () => {
    renderModal();
    expect(screen.getByText("Provider")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Attach Flows")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("shows 3 step labels in edit mode", () => {
    mockAttachmentsData = { flow_versions: [] };
    mockDeploymentDetail = makeDeployment();
    renderModal({ editingDeployment: makeDeployment() });
    expect(screen.queryByText("Provider")).not.toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Attach Flows")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });
});
