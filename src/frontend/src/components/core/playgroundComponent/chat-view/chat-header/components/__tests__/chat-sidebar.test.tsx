import { fireEvent, render, screen } from "@testing-library/react";
import { ChatSidebar } from "../chat-sidebar";

jest.mock(
  "@/components/core/playgroundComponent/hooks/use-get-flow-id",
  () => ({
    useGetFlowId: () => "flow-1",
  }),
);

type FlowState = { playgroundPage: boolean };
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: <TResult,>(selector: (state: FlowState) => TResult) =>
    selector({ playgroundPage: false }),
}));

type AlertState = { setSuccessData: jest.Mock };
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: <TResult,>(selector: (state: AlertState) => TResult) =>
    selector({ setSuccessData: jest.fn() }),
}));

jest.mock("../session-selector", () => ({
  SessionSelector: ({
    session,
    onToggleSelect,
  }: {
    session: string;
    onToggleSelect?: () => void;
  }) => (
    <button
      type="button"
      data-testid={`session-row-${session}`}
      onClick={onToggleSelect}
    >
      {session}
    </button>
  ),
}));

const baseProps = {
  sessions: ["flow-1", "New Session 0", "New Session 1"],
  onSessionSelect: jest.fn(),
  currentSessionId: "flow-1",
  onDeleteSession: jest.fn(),
  onRenameSession: jest.fn().mockResolvedValue(undefined),
  onBulkDeleteSessions: jest.fn(),
};

const checkAll = () =>
  fireEvent.click(screen.getByTestId("select-all-checkbox"));

describe("ChatSidebar — Select All row alignment", () => {
  it("does not render the bulk-delete button while nothing is selected", () => {
    render(<ChatSidebar {...baseProps} />);
    expect(screen.queryByTestId("bulk-delete-button")).not.toBeInTheDocument();
  });

  it("renders the bulk-delete button with the same h-8 w-8 p-2 shape as a SessionMoreMenu trigger", () => {
    render(<ChatSidebar {...baseProps} />);
    checkAll();
    const trash = screen.getByTestId("bulk-delete-button");
    expect(trash).toBeInTheDocument();
    expect(trash.className).toContain("h-8");
    expect(trash.className).toContain("w-8");
    expect(trash.className).toContain("p-2");
    // No leftover sm-button padding that would skew horizontal centering.
    expect(trash.className).not.toContain("p-0");
  });

  it("hosts the bulk-delete button in an h-8 row with no extra vertical padding", () => {
    render(<ChatSidebar {...baseProps} />);
    checkAll();
    const trash = screen.getByTestId("bulk-delete-button");
    // Walk up to the Select All row wrapper. Its className must include
    // `h-8` and must not add `py-1` / `py-*` padding that would push the
    // trash button's center down relative to the SessionSelector rows.
    const row = trash.closest("div.flex.items-center.justify-between");
    expect(row).not.toBeNull();
    expect(row!.className).toContain("h-8");
    expect(row!.className).not.toMatch(/\bpy-\d/);
    expect(row!.className).not.toMatch(/\bmb-\d/);
  });

  it("calls onBulkDeleteSessions with the checked sessions when clicked", () => {
    const onBulkDeleteSessions = jest.fn();
    render(
      <ChatSidebar
        {...baseProps}
        onBulkDeleteSessions={onBulkDeleteSessions}
      />,
    );
    checkAll();
    fireEvent.click(screen.getByTestId("bulk-delete-button"));
    expect(onBulkDeleteSessions).toHaveBeenCalledTimes(1);
    const [ids] = onBulkDeleteSessions.mock.calls[0];
    expect(ids).toEqual(
      expect.arrayContaining(["New Session 0", "New Session 1"]),
    );
    // Default session (currentFlowId) is non-selectable and must not be
    // included in the bulk delete payload.
    expect(ids).not.toContain("flow-1");
  });
});
