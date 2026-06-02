import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import type {
  Deployment,
  ProviderAccount,
} from "@/pages/MainPage/pages/deploymentsPage/types";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockDeploymentsData: { deployments: Deployment[] } | undefined = undefined;
let mockIsLoadingDeployments = false;
const mockPatchSnapshot = jest.fn();
const mockShowError = jest.fn();

// Simulate react-query caching: data is undefined until the first enabled
// fetch, then persists even when the query is later disabled.
let _deploymentsCache: { deployments: Deployment[] } | undefined = undefined;

jest.mock("@/controllers/API/queries/deployments/use-get-deployments", () => ({
  useGetDeployments: (_params: unknown, options?: { enabled?: boolean }) => {
    if (options?.enabled !== false && mockDeploymentsData !== undefined) {
      _deploymentsCache = mockDeploymentsData;
    }
    return {
      data:
        options?.enabled === false ? _deploymentsCache : mockDeploymentsData,
      isLoading: options?.enabled === false ? false : mockIsLoadingDeployments,
    };
  },
}));

jest.mock("@/controllers/API/queries/deployments", () => ({
  usePatchSnapshot: () => ({
    mutateAsync: mockPatchSnapshot,
  }),
}));

jest.mock(
  "@/pages/MainPage/pages/deploymentsPage/hooks/use-error-alert",
  () => ({
    useErrorAlert: () => mockShowError,
  }),
);

// biome-ignore lint/suspicious/noExplicitAny: test mock
let mockAttachmentsData: Record<string, any> | undefined = undefined;
let mockIsLoadingAttachments = false;
let mockIsFetchingAttachments = false;

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-attachments",
  () => ({
    useGetDeploymentAttachments: (
      _params: unknown,
      options?: { enabled?: boolean },
    ) => ({
      data: options?.enabled === false ? undefined : mockAttachmentsData,
      isLoading: options?.enabled === false ? false : mockIsLoadingAttachments,
      isFetching:
        options?.enabled === false ? false : mockIsFetchingAttachments,
    }),
  }),
);

// Stub StepDeployStatus to expose phase as text for assertions
jest.mock(
  "@/pages/MainPage/pages/deploymentsPage/components/step-deploy-status",
  () => ({
    __esModule: true,
    default: ({ phase }: { phase: string }) => (
      <div data-testid="step-deploy-status">{phase}</div>
    ),
  }),
);

import DeployChoiceDialog from "../index";

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

const makeProvider = (
  id = "p1",
  name = "WxO Prod",
  providerKey = "watsonx-orchestrate",
): ProviderAccount => ({
  id,
  name,
  provider_key: providerKey,
  provider_data: { url: "https://wxo.example.com" },
  created_at: null,
  updated_at: null,
});

const makeDeployment = (id = "dep-1", name = "My Bot"): Deployment => ({
  id,
  provider_id: "prov-1",
  description: null,
  type: "agent",
  created_at: "2025-01-01",
  updated_at: "2025-01-01",
  provider_data: { display_name: name, name: "my_bot" },
  resource_key: "my_bot",
  attached_count: 1,
});

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

interface RenderOptions {
  open?: boolean;
  providers?: ProviderAccount[];
  flowId?: string;
  snapshotVersionId?: string;
  snapshotVersionTag?: string;
  onTestDeployment?: jest.Mock;
}

function renderDialog(options: RenderOptions = {}) {
  const setOpen = jest.fn();
  const onChooseNew = jest.fn();
  const onUpdateComplete = jest.fn();
  const onTestDeployment = options.onTestDeployment ?? jest.fn();

  render(
    <TooltipProvider>
      <DeployChoiceDialog
        open={options.open ?? true}
        setOpen={setOpen}
        providers={options.providers ?? [makeProvider()]}
        flowId={options.flowId ?? "flow-1"}
        snapshotVersionId={options.snapshotVersionId ?? "snap-new"}
        snapshotVersionTag={options.snapshotVersionTag ?? "v2.0"}
        onChooseNew={onChooseNew}
        onUpdateComplete={onUpdateComplete}
        onTestDeployment={onTestDeployment}
      />
    </TooltipProvider>,
  );

  return { setOpen, onChooseNew, onUpdateComplete, onTestDeployment };
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  mockDeploymentsData = undefined;
  mockIsLoadingDeployments = false;
  _deploymentsCache = undefined;
  mockAttachmentsData = undefined;
  mockIsLoadingAttachments = false;
  mockIsFetchingAttachments = false;
  mockPatchSnapshot.mockResolvedValue({
    flow_version_id: "v-new",
    provider_snapshot_id: "snap-1",
  });
});

// ---------------------------------------------------------------------------
// Tests — closed state
// ---------------------------------------------------------------------------

describe("DeployChoiceDialog — closed state", () => {
  it("does not render dialog content when open is false", () => {
    renderDialog({ open: false });

    expect(screen.queryByText("Select Provider")).not.toBeInTheDocument();
    expect(screen.queryByText("Select Deployment")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — provider phase
// ---------------------------------------------------------------------------

describe("DeployChoiceDialog — provider phase", () => {
  it("shows provider phase title when 2+ providers given", () => {
    renderDialog({
      providers: [makeProvider("p1"), makeProvider("p2", "WxO Dev")],
    });

    expect(screen.getByText("Select Provider")).toBeInTheDocument();
  });

  it("renders all provider names", () => {
    renderDialog({
      providers: [
        makeProvider("p1", "WxO Prod"),
        makeProvider("p2", "WxO Dev"),
      ],
    });

    expect(screen.getByText("WxO Prod")).toBeInTheDocument();
    expect(screen.getByText("WxO Dev")).toBeInTheDocument();
  });

  it("Cancel button calls setOpen(false)", async () => {
    const user = userEvent.setup();
    const { setOpen } = renderDialog({
      providers: [makeProvider("p1"), makeProvider("p2", "WxO Dev")],
    });

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(setOpen).toHaveBeenCalledWith(false);
  });

  it("Continue button advances to deployments phase", async () => {
    const user = userEvent.setup();
    renderDialog({
      providers: [makeProvider("p1"), makeProvider("p2", "WxO Dev")],
    });

    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(screen.getByText("Select Deployment")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — deployments phase
// ---------------------------------------------------------------------------

describe("DeployChoiceDialog — deployments phase", () => {
  it("skips provider phase when exactly 1 provider", () => {
    renderDialog({ providers: [makeProvider()] });

    expect(screen.getByText("Select Deployment")).toBeInTheDocument();
    expect(screen.queryByText("Select Provider")).not.toBeInTheDocument();
  });

  it("always shows Create new deployment option", () => {
    renderDialog({ providers: [makeProvider()] });

    expect(screen.getByText("Create new deployment")).toBeInTheDocument();
  });

  it("shows existing deployment names from API data", () => {
    mockDeploymentsData = { deployments: [makeDeployment("d1", "Sales Bot")] };
    renderDialog({ providers: [makeProvider()] });

    expect(screen.getByText("Sales Bot")).toBeInTheDocument();
  });

  it("shows loading spinner when isLoadingDeployments is true", () => {
    mockIsLoadingDeployments = true;
    mockDeploymentsData = undefined;
    renderDialog({ providers: [makeProvider()] });

    // RadioGroup hidden, spinner shown — no deployment labels
    expect(screen.queryByText("Create new deployment")).not.toBeInTheDocument();
  });

  it("hides Back button when only 1 provider", () => {
    renderDialog({ providers: [makeProvider()] });

    expect(
      screen.queryByRole("button", { name: "Back" }),
    ).not.toBeInTheDocument();
  });

  it("shows Back button in deployments phase when 2+ providers", async () => {
    const user = userEvent.setup();
    renderDialog({
      providers: [makeProvider("p1"), makeProvider("p2", "WxO Dev")],
    });

    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(screen.getByRole("button", { name: "Back" })).toBeInTheDocument();
  });

  it("Back from deployments returns to provider phase", async () => {
    const user = userEvent.setup();
    renderDialog({
      providers: [makeProvider("p1"), makeProvider("p2", "WxO Dev")],
    });

    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByText("Select Deployment")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back" }));

    expect(screen.getByText("Select Provider")).toBeInTheDocument();
  });

  it("calls onChooseNew with provider preselection for known provider key", async () => {
    mockDeploymentsData = { deployments: [] };
    const { onChooseNew } = renderDialog({ providers: [makeProvider("p1")] });

    await waitFor(() =>
      expect(onChooseNew).toHaveBeenCalledWith({
        provider: {
          id: "watsonx",
          type: "watsonx",
          name: "watsonx Orchestrate",
          icon: "Bot",
        },
        instance: makeProvider("p1"),
      }),
    );
  });

  it("auto-skips deployments phase after provider select when no deployments exist", async () => {
    const user = userEvent.setup();
    mockDeploymentsData = { deployments: [] };
    const { onChooseNew } = renderDialog({
      providers: [makeProvider("p1"), makeProvider("p2", "WxO Dev")],
    });

    await user.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(onChooseNew).toHaveBeenCalledWith({
        provider: {
          id: "watsonx",
          type: "watsonx",
          name: "watsonx Orchestrate",
          icon: "Bot",
        },
        instance: makeProvider("p1"),
      }),
    );
  });

  it("reopens on provider selection after close instead of auto-skipping from stale state", async () => {
    const user = userEvent.setup();
    mockDeploymentsData = { deployments: [] };
    const onChooseNew = jest.fn();
    const onUpdateComplete = jest.fn();
    const setOpen = jest.fn();

    const { rerender } = render(
      <TooltipProvider>
        <DeployChoiceDialog
          open
          setOpen={setOpen}
          providers={[makeProvider("p1"), makeProvider("p2", "WxO Dev")]}
          flowId="flow-1"
          snapshotVersionId="snap-new"
          snapshotVersionTag="v2.0"
          onChooseNew={onChooseNew}
          onUpdateComplete={onUpdateComplete}
          onTestDeployment={jest.fn()}
        />
      </TooltipProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(onChooseNew).toHaveBeenCalledTimes(1));

    rerender(
      <TooltipProvider>
        <DeployChoiceDialog
          open={false}
          setOpen={setOpen}
          providers={[makeProvider("p1"), makeProvider("p2", "WxO Dev")]}
          flowId="flow-1"
          snapshotVersionId="snap-new"
          snapshotVersionTag="v2.0"
          onChooseNew={onChooseNew}
          onUpdateComplete={onUpdateComplete}
          onTestDeployment={jest.fn()}
        />
      </TooltipProvider>,
    );

    rerender(
      <TooltipProvider>
        <DeployChoiceDialog
          open
          setOpen={setOpen}
          providers={[makeProvider("p1"), makeProvider("p2", "WxO Dev")]}
          flowId="flow-1"
          snapshotVersionId="snap-new"
          snapshotVersionTag="v2.0"
          onChooseNew={onChooseNew}
          onUpdateComplete={onUpdateComplete}
          onTestDeployment={jest.fn()}
        />
      </TooltipProvider>,
    );

    expect(screen.getByText("Select Provider")).toBeInTheDocument();
    expect(onChooseNew).toHaveBeenCalledTimes(1);
  });

  it("calls onChooseNew with undefined when provider key has no mapping", async () => {
    mockDeploymentsData = { deployments: [] };
    const { onChooseNew } = renderDialog({
      providers: [makeProvider("p1", "Unknown", "some-unknown-provider")],
    });

    await waitFor(() => expect(onChooseNew).toHaveBeenCalledWith(undefined));
  });

  it("auto-selects the single existing attachment", async () => {
    const user = userEvent.setup();
    mockDeploymentsData = { deployments: [makeDeployment()] };
    mockAttachmentsData = {
      flow_versions: [
        {
          id: "v-1",
          flow_id: "flow-1",
          flow_name: "My Flow",
          version_number: 1,
          attached_at: "2025-01-01",
          provider_snapshot_id: "snap-1",
          provider_data: null,
        },
      ],
      page: 1,
      size: 50,
      total: 1,
    };
    renderDialog({ providers: [makeProvider()] });

    // Clicking Continue should go to review (not call onChooseNew) because
    // the single attachment was auto-selected instead of __new__
    await user.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(screen.getByText("Update Deployment")).toBeInTheDocument(),
    );
  });

  it("advances to review phase when existing attachment selected and continued", async () => {
    const user = userEvent.setup();
    mockDeploymentsData = {
      deployments: [makeDeployment("dep-1", "My Bot")],
    };
    mockAttachmentsData = {
      flow_versions: [
        {
          id: "v-1",
          flow_id: "flow-1",
          flow_name: "My Flow",
          version_number: 1,
          attached_at: "2025-01-01",
          provider_snapshot_id: "snap-1",
          provider_data: null,
        },
      ],
      page: 1,
      size: 50,
      total: 1,
    };
    renderDialog({ providers: [makeProvider()] });

    await user.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(screen.getByText("Update Deployment")).toBeInTheDocument(),
    );
  });
});

// ---------------------------------------------------------------------------
// Tests — review phase
// ---------------------------------------------------------------------------

describe("DeployChoiceDialog — review phase", () => {
  let user: ReturnType<typeof userEvent.setup>;
  let callbacks: ReturnType<typeof renderDialog>;

  beforeEach(async () => {
    mockDeploymentsData = {
      deployments: [makeDeployment("dep-1", "My Bot")],
    };
    mockAttachmentsData = {
      flow_versions: [
        {
          id: "v-1",
          flow_id: "flow-1",
          flow_name: "My Flow",
          version_number: 1,
          attached_at: "2025-01-01",
          provider_snapshot_id: "snap-1",
          provider_data: null,
        },
      ],
      page: 1,
      size: 50,
      total: 1,
    };
    user = userEvent.setup();
    callbacks = renderDialog({
      providers: [makeProvider("p1")],
      snapshotVersionId: "snap-new",
      snapshotVersionTag: "v2.0",
    });
    // Single attachment auto-selected; Continue goes straight to review
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(screen.getByText("Update Deployment")).toBeInTheDocument(),
    );
  });

  it("shows Update Deployment title", () => {
    expect(screen.getByText("Update Deployment")).toBeInTheDocument();
  });

  it("shows spinner while loading review attachment details", async () => {
    cleanup();
    mockDeploymentsData = {
      deployments: [makeDeployment("dep-1", "My Bot", "snap-1", "v-1")],
    };
    mockAttachmentsData = undefined;
    mockIsLoadingAttachments = true;

    const user = userEvent.setup();
    renderDialog({
      providers: [makeProvider("p1")],
      snapshotVersionId: "snap-new",
      snapshotVersionTag: "v2.0",
    });

    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(screen.getByTestId("review-loading-skeleton")).toBeInTheDocument();
  });

  it("shows deployment name", () => {
    expect(screen.getByText("My Bot")).toBeInTheDocument();
  });

  it("shows current version tag from API", () => {
    expect(screen.getAllByText("v1").length).toBeGreaterThan(0);
  });

  it("shows new version tag from props", () => {
    expect(screen.getByText("v2.0")).toBeInTheDocument();
  });

  it("shows compact deployed tool summary when there is only one attachment", () => {
    expect(screen.getByText("My Flow")).toBeInTheDocument();
    expect(
      screen.queryByText("Choose deployed version"),
    ).not.toBeInTheDocument();
  });

  it("Back button returns to deployments phase", async () => {
    await user.click(screen.getByRole("button", { name: "Back" }));

    expect(screen.getByText("Select Deployment")).toBeInTheDocument();
  });

  it("Cancel button calls setOpen(false)", async () => {
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(callbacks.setOpen).toHaveBeenCalledWith(false);
  });

  it("Update button calls patchSnapshot with correct args", async () => {
    await user.click(
      screen.getByRole("button", { name: "Replace v1 with v2.0" }),
    );

    expect(mockPatchSnapshot).toHaveBeenCalledWith({
      providerSnapshotId: "snap-1",
      flowVersionId: "snap-new",
    });
  });

  it("lets user choose exact attached version when deployment has many", async () => {
    cleanup();
    mockDeploymentsData = {
      deployments: [makeDeployment("dep-1", "My Bot", "snap-1", "v-1")],
    };
    mockAttachmentsData = {
      flow_versions: [
        {
          id: "v-1",
          flow_id: "flow-1",
          flow_name: "My Flow",
          version_number: 1,
          attached_at: "2025-01-01",
          provider_snapshot_id: "snap-1",
          provider_data: { tool_name: "My Flow old" },
        },
        {
          id: "v-2",
          flow_id: "flow-1",
          flow_name: "My Flow",
          version_number: 2,
          attached_at: "2025-01-02",
          provider_snapshot_id: "snap-2",
          provider_data: { tool_name: "My Flow current" },
        },
      ],
      page: 1,
      size: 50,
      total: 2,
    };

    const localUser = userEvent.setup();
    renderDialog({
      providers: [makeProvider("p1")],
      snapshotVersionId: "snap-new",
      snapshotVersionTag: "v3.0",
    });

    await localUser.click(screen.getByRole("button", { name: "Continue" }));

    await waitFor(() =>
      expect(screen.getByText("Select version to replace")).toBeInTheDocument(),
    );

    await localUser.click(
      screen.getByRole("radio", { name: /My Flow current/ }),
    );
    await localUser.click(
      screen.getByRole("button", { name: "Replace v2 with v3.0" }),
    );

    await waitFor(() =>
      expect(mockPatchSnapshot).toHaveBeenCalledWith({
        providerSnapshotId: "snap-2",
        flowVersionId: "snap-new",
      }),
    );
  });

  it("shows deploying state immediately after clicking Update", async () => {
    let resolve!: (v: unknown) => void;
    mockPatchSnapshot.mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );

    await user.click(
      screen.getByRole("button", { name: "Replace v1 with v2.0" }),
    );

    expect(screen.getByTestId("step-deploy-status")).toHaveTextContent(
      "deploying",
    );
    resolve({});
  });

  it("shows deployed state after patchSnapshot resolves", async () => {
    await user.click(
      screen.getByRole("button", { name: "Replace v1 with v2.0" }),
    );

    await waitFor(() =>
      expect(screen.getByTestId("step-deploy-status")).toHaveTextContent(
        "deployed",
      ),
    );
  });

  it("calls showError and returns to review when patchSnapshot fails", async () => {
    mockPatchSnapshot.mockRejectedValue(new Error("Network error"));

    await user.click(
      screen.getByRole("button", { name: "Replace v1 with v2.0" }),
    );

    await waitFor(() =>
      expect(mockShowError).toHaveBeenCalledWith(
        "Failed to update deployment",
        expect.any(Error),
      ),
    );
    expect(screen.getByText("Update Deployment")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests — update phase
// ---------------------------------------------------------------------------

describe("DeployChoiceDialog — update phase", () => {
  let user: ReturnType<typeof userEvent.setup>;
  let callbacks: ReturnType<typeof renderDialog>;

  beforeEach(async () => {
    mockDeploymentsData = {
      deployments: [makeDeployment("dep-1", "My Bot")],
    };
    mockAttachmentsData = {
      flow_versions: [
        {
          id: "v-1",
          flow_id: "flow-1",
          flow_name: "My Flow",
          version_number: 1,
          attached_at: "2025-01-01",
          provider_snapshot_id: "snap-1",
          provider_data: null,
        },
      ],
      page: 1,
      size: 50,
      total: 1,
    };
    mockPatchSnapshot.mockResolvedValue({});
    user = userEvent.setup();
    callbacks = renderDialog({ providers: [makeProvider("p1")] });

    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() =>
      expect(screen.getByText("Update Deployment")).toBeInTheDocument(),
    );
    await user.click(
      screen.getByRole("button", { name: "Replace v1 with v2.0" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("step-deploy-status")).toHaveTextContent(
        "deployed",
      ),
    );
  });

  it("shows Close button after update completes", () => {
    // getAllByRole because Radix Dialog's X button also has accessible name "Close"
    const closeButtons = screen.getAllByRole("button", { name: "Close" });
    // Our custom Close button (no SVG icon) is the first one in DOM order
    const customClose = closeButtons.find((btn) => !btn.querySelector("svg"));
    expect(customClose).toBeInTheDocument();
  });

  it("Close button calls onUpdateComplete with deployment name", async () => {
    const closeButtons = screen.getAllByRole("button", { name: "Close" });
    const customClose = closeButtons.find((btn) => !btn.querySelector("svg"))!;
    await user.click(customClose);

    expect(callbacks.onUpdateComplete).toHaveBeenCalledWith("My Bot");
  });

  it("shows Test button when onTestDeployment is provided", () => {
    expect(screen.getByRole("button", { name: "Test" })).toBeInTheDocument();
  });

  it("Test button calls onTestDeployment with deployment id and provider id", async () => {
    await user.click(screen.getByRole("button", { name: "Test" }));

    expect(callbacks.onTestDeployment).toHaveBeenCalledWith(
      { id: "dep-1", name: "My Bot" },
      "p1",
    );
  });
});
