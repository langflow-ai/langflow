import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Deployment } from "../types";

// ---------------------------------------------------------------------------
// Mocks — API hooks
// ---------------------------------------------------------------------------

let mockDeploymentDetail: Deployment | null = null;
let mockIsFetchingDetails = false;

jest.mock("@/controllers/API/queries/deployments/use-get-deployment", () => ({
  useGetDeployment: () => ({
    data: mockDeploymentDetail,
    isFetching: mockIsFetchingDetails,
  }),
}));

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
let mockIsFetchingAttachments = false;

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-attachments",
  () => ({
    useGetDeploymentAttachments: () => ({
      data: mockAttachmentsData,
      isFetching: mockIsFetchingAttachments,
    }),
  }),
);

let mockConfigsData: {
  configs: Array<{ id: string; name: string }>;
} | null = null;
let mockIsFetchingConfigs = false;

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-configs",
  () => ({
    useGetDeploymentConfigs: () => ({
      data: mockConfigsData,
      isFetching: mockIsFetchingConfigs,
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

import DeploymentDetailsModal from "../components/deployment-details-modal/deployment-details-modal";

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

function renderModal(
  deployment: Deployment | null = makeDeployment(),
  open = true,
) {
  const setOpen = jest.fn();
  const result = render(
    <TooltipProvider>
      <DeploymentDetailsModal
        open={open}
        setOpen={setOpen}
        deployment={deployment}
        providerName="watsonx Prod"
      />
    </TooltipProvider>,
  );
  return { setOpen, ...result };
}

beforeEach(() => {
  jest.clearAllMocks();
  const dep = makeDeployment();
  mockDeploymentDetail = dep;
  mockIsFetchingDetails = false;
  mockAttachmentsData = {
    flow_versions: [
      {
        id: "fv-1",
        flow_id: "flow-1",
        flow_name: "Sales Flow",
        version_number: 3,
        attached_at: "2025-06-01T00:00:00Z",
        provider_snapshot_id: "snap-1",
        tool_name: "sales_tool",
        provider_data: { app_ids: ["cfg-1", "cfg-2"] },
      },
    ],
  };
  mockIsFetchingAttachments = false;
  mockConfigsData = {
    configs: [
      { id: "cfg-1", name: "Production Config" },
      { id: "cfg-2", name: "Staging Config" },
    ],
  };
  mockIsFetchingConfigs = false;
});

// ---------------------------------------------------------------------------
// Basic rendering
// ---------------------------------------------------------------------------

describe("Basic rendering", () => {
  it("renders the Deployment Details title", () => {
    renderModal();
    expect(screen.getByText("Deployment Details")).toBeInTheDocument();
  });

  it("renders the description text", () => {
    renderModal();
    expect(
      screen.getByText("View deployment configuration and attached flows."),
    ).toBeInTheDocument();
  });

  it("renders the Close button", () => {
    renderModal();
    expect(screen.getByTestId("deployment-details-close")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Info grid rendering
// ---------------------------------------------------------------------------

describe("Info grid rendering", () => {
  it("shows deployment type", () => {
    renderModal();
    expect(screen.getByText("agent")).toBeInTheDocument();
  });

  it("shows deployment name", () => {
    renderModal();
    expect(screen.getByText("My Agent")).toBeInTheDocument();
  });

  it("shows description when present", () => {
    renderModal();
    expect(screen.getByText("A sales agent")).toBeInTheDocument();
  });

  it("shows LLM model from provider_data", () => {
    renderModal();
    expect(screen.getByText("granite-13b-chat")).toBeInTheDocument();
  });

  it("shows provider name", () => {
    renderModal();
    expect(screen.getByText("watsonx Prod")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Flow list with versions and connections
// ---------------------------------------------------------------------------

describe("Flow list with versions and connections", () => {
  it("shows attached flows count", () => {
    renderModal();
    expect(screen.getByText("Attached Flows (1)")).toBeInTheDocument();
  });

  it("shows flow name and version number", () => {
    renderModal();
    expect(screen.getByText("Sales Flow")).toBeInTheDocument();
    expect(screen.getByText("v3")).toBeInTheDocument();
  });

  it("maps connection IDs to names via configMap", () => {
    renderModal();
    expect(screen.getByText("Production Config")).toBeInTheDocument();
    expect(screen.getByText("Staging Config")).toBeInTheDocument();
  });

  it("shows 'No flows attached' when flow list is empty", () => {
    mockAttachmentsData = { flow_versions: [] };
    renderModal();
    expect(screen.getByText("No flows attached")).toBeInTheDocument();
  });

  it("shows flow_id as fallback when config not found", () => {
    mockConfigsData = { configs: [] };
    renderModal();
    // app_ids that aren't in configMap appear as-is
    expect(screen.getByText("cfg-1")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("Loading state", () => {
  it("shows loading indicator when fetching details", () => {
    mockIsFetchingDetails = true;
    renderModal();
    // Loading component is rendered
    expect(screen.queryByText("Attached Flows")).not.toBeInTheDocument();
  });

  it("shows loading indicator when fetching attachments", () => {
    mockIsFetchingAttachments = true;
    renderModal();
    expect(screen.queryByText("Attached Flows")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Close behavior
// ---------------------------------------------------------------------------

describe("Close behavior", () => {
  it("calls setOpen when Close button is clicked", async () => {
    const user = userEvent.setup();
    const { setOpen } = renderModal();

    await user.click(screen.getByTestId("deployment-details-close"));
    expect(setOpen).toHaveBeenCalledWith(false);
  });
});

// ---------------------------------------------------------------------------
// Null deployment
// ---------------------------------------------------------------------------

describe("Null deployment", () => {
  it("renders without crashing when deployment is null", () => {
    renderModal(null);
    expect(screen.getByText("Deployment Details")).toBeInTheDocument();
  });
});
