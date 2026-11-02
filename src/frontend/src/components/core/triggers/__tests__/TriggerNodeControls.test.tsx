import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConnectionRead } from "@/controllers/API/queries/connections";
import type { TriggerRead } from "@/controllers/API/queries/triggers";
import TriggerNodeControls from "../TriggerNodeControls";
import { makeTrigger } from "./fixtures";

let mockTrigger: TriggerRead | undefined;
let mockConnections: Partial<ConnectionRead>[] = [];
const mockEnable = jest.fn();
const mockDisable = jest.fn();
const mockUpdateConnection = jest.fn();

jest.mock("../hooks/use-node-trigger", () => ({
  useNodeTrigger: () => ({ trigger: mockTrigger, isLoading: false }),
}));
jest.mock("@/controllers/API/queries/triggers", () => ({
  useEnableTriggerMutation: () => ({
    mutateAsync: mockEnable,
    isPending: false,
  }),
  useDisableTriggerMutation: () => ({
    mutateAsync: mockDisable,
    isPending: false,
  }),
}));
jest.mock("@/controllers/API/queries/connections", () => ({
  useGetConnections: () => ({ data: mockConnections }),
  useUpdateConnectionMutation: () => ({
    mutateAsync: mockUpdateConnection,
    isPending: false,
  }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));

const connection = (allow: boolean) => ({
  id: "conn-1",
  display_name: "Eng Slack bot",
  allow_non_interactive: allow,
});

describe("TriggerNodeControls", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockConnections = [];
  });

  it("asks for a save before the trigger row exists", () => {
    mockTrigger = undefined;
    render(<TriggerNodeControls nodeId="n1" />);

    expect(screen.getByTestId("trigger-node-unsaved")).toHaveTextContent(
      "Save the flow to create this trigger.",
    );
  });

  it("holds Enabled until background runs are allowed, and says why", async () => {
    mockTrigger = makeTrigger({
      state: "pending",
      reason: "pending",
      allowed_actions: ["pause", "resume", "delete"],
    });
    mockConnections = [connection(false)];
    render(<TriggerNodeControls nodeId="n1" />);
    const enabled = screen.getByRole("switch", { name: "Enabled" });

    expect(enabled).toHaveAttribute("aria-disabled", "true");
    expect(enabled).toHaveAccessibleDescription("Allow background runs first.");
    await userEvent.click(enabled);
    expect(mockEnable).not.toHaveBeenCalled();
  });

  it("grants consent only when the user turns it on, never as a side effect", async () => {
    mockTrigger = makeTrigger({
      state: "pending",
      allowed_actions: ["resume"],
    });
    mockConnections = [connection(false)];
    render(<TriggerNodeControls nodeId="n1" />);

    expect(mockUpdateConnection).not.toHaveBeenCalled();
    await userEvent.click(
      screen.getByRole("switch", { name: "Allow background runs" }),
    );
    expect(mockUpdateConnection).toHaveBeenCalledWith({
      id: "conn-1",
      patch: { allow_non_interactive: true },
    });
  });

  it("enables a pending trigger once consent is in place", async () => {
    mockTrigger = makeTrigger({
      state: "pending",
      allowed_actions: ["pause", "resume"],
    });
    mockConnections = [connection(true)];
    mockEnable.mockResolvedValue({});
    render(<TriggerNodeControls nodeId="n1" />);

    await userEvent.click(screen.getByRole("switch", { name: "Enabled" }));
    expect(mockEnable).toHaveBeenCalledWith("trg-1");
  });

  it("pauses an active trigger", async () => {
    mockTrigger = makeTrigger();
    mockConnections = [connection(true)];
    mockDisable.mockResolvedValue({});
    render(<TriggerNodeControls nodeId="n1" />);
    const enabled = screen.getByRole("switch", { name: "Enabled" });

    expect(enabled).toBeChecked();
    await userEvent.click(enabled);
    expect(mockDisable).toHaveBeenCalledWith("trg-1");
  });

  it("tells a non-owner who can grant consent instead of offering the switch", () => {
    mockTrigger = makeTrigger();
    mockConnections = [];
    render(<TriggerNodeControls nodeId="n1" />);

    expect(
      screen.getByText(
        "Only the connection's owner can allow background runs.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("switch", { name: "Allow background runs" }),
    ).toBeNull();
  });

  it("shows the server's reason when the toggle is blocked", () => {
    mockTrigger = makeTrigger({
      allowed_actions: [],
      blocked_actions: { pause: "insufficient_permission" },
    });
    mockConnections = [connection(true)];
    render(<TriggerNodeControls nodeId="n1" />);

    expect(
      screen.getByRole("switch", { name: "Enabled" }),
    ).toHaveAccessibleDescription(
      "You don't have permission to do this on this flow.",
    );
  });

  it("has no consent row for a trigger without a connection", () => {
    mockTrigger = makeTrigger({
      connection_id: null,
      provider: null,
      kind: "schedule",
    });
    render(<TriggerNodeControls nodeId="n1" />);

    expect(screen.queryByText("Allow background runs")).toBeNull();
  });
});
