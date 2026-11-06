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
const mockEnable = jest.fn();
const mockDisable = jest.fn();
const mockTest = jest.fn();
const mockNavigate = jest.fn();

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
    useEnableTriggerMutation: () => ({
      mutateAsync: mockEnable,
      isPending: false,
    }),
    useDisableTriggerMutation: () => ({
      mutateAsync: mockDisable,
      isPending: false,
    }),
    useDeleteTriggerMutation: mutation,
    useTestTriggerMutation: () => ({
      mutateAsync: mockTest,
      isPending: false,
    }),
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
  useCustomNavigate: () => mockNavigate,
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

  it.each(["reader", "writer"] as const)(
    "renders a shared trigger using the server's %s permissions",
    async (role) => {
      const canWrite = role === "writer";
      const blockedActions: TriggerRead["blocked_actions"] = {
        test: "insufficient_permission",
        replay: "insufficient_permission",
      };
      if (!canWrite) {
        blockedActions.pause = "insufficient_permission";
        blockedActions.delete = "insufficient_permission";
      }
      mockMine = [
        makeTrigger({
          id: "shared",
          user_id: "user-other",
          name: "Shared schedule",
          kind: "schedule",
          provider: null,
          connection_id: null,
          allowed_actions: canWrite ? ["pause", "delete"] : [],
          blocked_actions: blockedActions,
        }),
      ];
      mockDisable.mockResolvedValue(mockMine[0]);
      const user = userEvent.setup();
      render(<TriggersPage />);

      const row = screen.getByTestId("trigger-row-shared");
      expect(within(row).getByText("Shared schedule")).toBeInTheDocument();
      const test = within(row).getByTestId("trigger-test-shared");
      expect(test).toHaveAttribute("aria-disabled", "true");
      expect(test).toHaveAccessibleDescription(
        "You don't have permission to do this on this flow.",
      );
      await user.click(test);
      expect(mockTest).not.toHaveBeenCalled();

      await user.click(within(row).getByTestId("trigger-menu-shared"));
      const pause = screen.getByTestId("trigger-action-pause");
      const remove = screen.getByTestId("trigger-action-delete");
      if (canWrite) {
        expect(pause).not.toHaveAttribute("aria-disabled");
        expect(remove).not.toHaveAttribute("aria-disabled");
        await user.click(pause);
        expect(mockDisable).toHaveBeenCalledWith("shared");
      } else {
        for (const action of [pause, remove]) {
          expect(action).toHaveAttribute("aria-disabled", "true");
          expect(action).toHaveAccessibleDescription(
            "You don't have permission to do this on this flow.",
          );
          await user.click(action);
        }
        expect(mockDisable).not.toHaveBeenCalled();
        expect(
          screen.queryByTestId("btn_delete_delete_confirmation_modal"),
        ).toBeNull();
      }
    },
  );

  it("opens connection settings without resuming a revoked trigger", async () => {
    mockMine = [
      makeTrigger({
        id: "revoked",
        state: "needs_reconnect",
        reason: "needs_reconnect",
        allowed_actions: ["pause", "reconnect", "delete"],
        blocked_actions: { resume: "needs_reconnect" },
      }),
    ];
    render(<TriggersPage />);

    await userEvent.click(
      screen.getByRole("button", { name: "Reconnect Slack: On Message" }),
    );

    expect(mockNavigate).toHaveBeenCalledWith("/settings/connections");
    expect(mockEnable).not.toHaveBeenCalled();
  });

  it("resumes a reconnected Jira trigger only after its inline fix is clicked", async () => {
    mockMine = [
      makeTrigger({
        id: "jira-reconnected",
        name: "Jira: On Issue Created",
        provider: "jira",
        kind: "jira.issue_created",
        state: "needs_reconnect",
        reason: "ready_to_resume",
        allowed_actions: ["pause", "resume", "delete"],
        blocked_actions: { reconnect: "reconnect_not_needed" },
      }),
    ];
    mockEnable.mockResolvedValue(mockMine[0]);
    render(<TriggersPage />);

    expect(mockEnable).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("button", { name: "Resume Jira: On Issue Created" }),
    );

    expect(mockEnable).toHaveBeenCalledWith("jira-reconnected");
    expect(mockNavigate).not.toHaveBeenCalled();
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
