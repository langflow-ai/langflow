import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { makeTrigger } from "@/components/core/triggers/__tests__/fixtures";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import TriggersPage from "../index";

let mockUser = { id: "user-1", is_superuser: false };
let mockMine: TriggerRead[] = [];
let mockAll: TriggerRead[] = [];
const mockBulk = jest.fn();
const mockDryRun = jest.fn();

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/controllers/API/queries/triggers", () => {
  const mutation = () => ({ mutateAsync: jest.fn(), isPending: false });
  return {
    TRIGGER_EVENTS_PAGE_SIZE: 50,
    useTriggersQuery: (params: { scope?: string }) => ({
      data: params.scope === "all" ? mockAll : mockMine,
      isLoading: false,
      isError: false,
    }),
    useTriggerQuery: () => ({ data: undefined }),
    useTriggerEventsQuery: () => ({ data: [], isLoading: false }),
    useTriggerIngressQuery: () => ({ data: undefined }),
    useTriggerPollingInterval: () => 5000,
    useEnableTriggerMutation: mutation,
    useDisableTriggerMutation: mutation,
    useDeleteTriggerMutation: mutation,
    useTestTriggerMutation: mutation,
    useReplayTriggerEventMutation: mutation,
    useRotateSigningSecretMutation: () => ({ reset: jest.fn() }),
    useBulkTriggersMutation: () => ({
      mutateAsync: mockBulk,
      isPending: false,
    }),
    useBulkTriggersDryRunMutation: () => ({
      mutate: mockDryRun,
      reset: jest.fn(),
      data: { changed: ["a", "b"], unchanged: ["c"], failed: [], owners: 2 },
      isPending: false,
      isError: false,
    }),
  };
});
jest.mock("@/controllers/API/queries/connections", () => ({
  useGetConnections: () => ({
    data: [{ id: "conn-1", display_name: "Eng Slack bot" }],
  }),
  useUpdateConnectionMutation: () => ({ mutateAsync: jest.fn() }),
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ userData: mockUser }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn(), setSuccessData: jest.fn() }),
}));

// Radix Select reads pointer capture, which jsdom does not implement.
beforeAll(() => {
  Element.prototype.hasPointerCapture ??= () => false;
  Element.prototype.releasePointerCapture ??= () => undefined;
  Element.prototype.scrollIntoView ??= () => undefined;
});

describe("TriggersPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUser = { id: "user-1", is_superuser: false };
    mockMine = [
      makeTrigger({ id: "a" }),
      makeTrigger({
        id: "b",
        flow_name: "Inbox to CRM",
        name: "Outlook: On Message",
        provider: "microsoft",
        connection_id: "conn-other",
        config: { mechanism_id: "microsoft.graph_delta_poll" },
        state: "needs_reconnect",
        reason: "needs_reconnect",
        allowed_actions: ["pause", "reconnect", "delete"],
      }),
      makeTrigger({
        id: "c",
        flow_name: "Daily digest",
        name: "Schedule",
        kind: "schedule",
        provider: null,
        connection_id: null,
        config: {},
      }),
    ];
    mockAll = [];
  });

  it("lists triggers with flow, source, transport, connection and state", () => {
    render(<TriggersPage />);
    const row = screen.getByTestId("trigger-row-a");

    expect(within(row).getByText("Support triage")).toBeInTheDocument();
    expect(within(row).getByText("Push")).toBeInTheDocument();
    expect(within(row).getByText("Eng Slack bot")).toBeInTheDocument();
    expect(within(row).getByTestId("trigger-state-badge")).toHaveTextContent(
      "Active",
    );
    expect(
      within(screen.getByTestId("trigger-row-b")).getByText(
        "Not visible to you",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("trigger-row-c")).getByText("Not needed"),
    ).toBeInTheDocument();
  });

  it("narrows to triggers that need attention", async () => {
    render(<TriggersPage />);

    await userEvent.click(screen.getByTestId("triggers-attention-toggle"));

    expect(screen.queryByTestId("trigger-row-a")).toBeNull();
    expect(screen.getByTestId("trigger-row-b")).toBeInTheDocument();
  });

  it("explains an empty search", async () => {
    render(<TriggersPage />);

    await userEvent.type(screen.getByTestId("triggers-search"), "zzz");

    expect(screen.getByTestId("triggers-empty")).toHaveTextContent(
      "No triggers match these filters.",
    );
  });

  it("hides the operator tab from a regular user", () => {
    render(<TriggersPage />);

    expect(screen.queryByRole("tab", { name: "All triggers" })).toBeNull();
  });

  it("lets a superuser pause every trigger on a provider after a dry run", async () => {
    mockUser = { id: "admin", is_superuser: true };
    mockAll = [
      makeTrigger({ id: "a", owner_username: "eric" }),
      makeTrigger({ id: "b", owner_username: "priya" }),
    ];
    mockBulk.mockResolvedValue({ changed: ["a", "b"], failed: [] });
    const user = userEvent.setup();
    render(<TriggersPage />);

    await user.click(screen.getByRole("tab", { name: "All triggers" }));
    expect(screen.getByText("priya")).toBeInTheDocument();
    expect(screen.getByTestId("triggers-bulk-pause")).toBeDisabled();

    await user.click(screen.getByTestId("triggers-provider-filter"));
    await user.click(screen.getByRole("option", { name: "Slack" }));
    await user.click(screen.getByTestId("triggers-bulk-pause"));

    expect(mockDryRun).toHaveBeenCalledWith({
      action: "pause",
      body: { provider: "slack" },
    });
    expect(screen.getByTestId("triggers-bulk-dialog")).toHaveTextContent(
      "Pause 2 active Slack triggers?",
    );
    await user.click(screen.getByTestId("triggers-bulk-confirm"));
    expect(mockBulk).toHaveBeenCalledWith({
      action: "pause",
      body: { provider: "slack" },
    });
  });
});
