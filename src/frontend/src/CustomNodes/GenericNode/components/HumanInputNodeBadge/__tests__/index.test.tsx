import { act, fireEvent, render, screen } from "@testing-library/react";
import { useHitlStore } from "@/stores/hitlStore";
import type { InteractiveContent } from "@/types/chat";
import HumanInputNodeBadge from "../index";

jest.mock("@/components/core/chatComponents/HumanInputCard", () => ({
  __esModule: true,
  default: () => <div data-testid="hitl-card" />,
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => <span />,
}));
jest.mock("@/components/ui/popover", () => ({
  Popover: ({
    children,
    open,
    onOpenChange,
  }: {
    children: React.ReactNode;
    open: boolean;
    onOpenChange: (open: boolean) => void;
  }) => (
    <div data-testid="popover-root" data-open={String(open)}>
      <button
        type="button"
        data-testid="popover-dismiss"
        onClick={() => onOpenChange(false)}
      />
      {children}
    </div>
  ),
  PopoverAnchor: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  PopoverContentWithoutPortal: ({
    children,
  }: {
    children: React.ReactNode;
  }) => <div>{children}</div>,
}));

const _content: InteractiveContent = {
  type: "human_input",
  kind: "node_input",
  request_id: "HumanInput-abc:job-1",
  prompt: "Approve?",
  options: [{ action_id: "approve", label: "Approve" }],
  allowed_decisions: ["approve"],
  job_id: "job-1",
};

describe("HumanInputNodeBadge", () => {
  afterEach(() => useHitlStore.getState().clear());

  it("renders nothing when no node is awaiting input", () => {
    render(<HumanInputNodeBadge nodeId="HumanInput-abc" />);
    expect(
      screen.queryByTestId("human-input-node-badge"),
    ).not.toBeInTheDocument();
  });

  it("renders the badge + card on the node whose id matches the pending request", () => {
    useHitlStore
      .getState()
      .setPending({ nodeId: "HumanInput-abc", content: _content });
    render(<HumanInputNodeBadge nodeId="HumanInput-abc" />);
    expect(screen.getByTestId("human-input-node-badge")).toBeInTheDocument();
    expect(screen.getByTestId("hitl-card")).toBeInTheDocument();
  });

  it("uses the run control's click target, not the bare 14px icon", () => {
    // PDF item 2: the pause affordance sits in the run-button slot and must
    // match its size/style — button-run-bg supplies the 24x24 hover target.
    useHitlStore
      .getState()
      .setPending({ nodeId: "HumanInput-abc", content: _content });
    render(<HumanInputNodeBadge nodeId="HumanInput-abc" />);
    expect(screen.getByTestId("human-input-node-badge")).toHaveClass(
      "button-run-bg",
    );
  });

  it("reopens the dismissed popover when a NEW pause request arrives", () => {
    // Rerunning a paused flow supersedes the old pause with a new request_id;
    // the popover must resurface for it even though the badge never unmounted.
    useHitlStore
      .getState()
      .setPending({ nodeId: "HumanInput-abc", content: _content });
    render(<HumanInputNodeBadge nodeId="HumanInput-abc" />);
    expect(screen.getByTestId("popover-root")).toHaveAttribute(
      "data-open",
      "true",
    );

    fireEvent.click(screen.getByTestId("popover-dismiss"));
    expect(screen.getByTestId("popover-root")).toHaveAttribute(
      "data-open",
      "false",
    );

    act(() => {
      useHitlStore.getState().setPending({
        nodeId: "HumanInput-abc",
        content: {
          ..._content,
          request_id: "HumanInput-abc:job-2",
          job_id: "job-2",
        },
      });
    });
    expect(screen.getByTestId("popover-root")).toHaveAttribute(
      "data-open",
      "true",
    );
  });

  it("renders nothing on a node that is not the one awaiting input", () => {
    useHitlStore
      .getState()
      .setPending({ nodeId: "HumanInput-abc", content: _content });
    render(<HumanInputNodeBadge nodeId="ChatOutput-xyz" />);
    expect(
      screen.queryByTestId("human-input-node-badge"),
    ).not.toBeInTheDocument();
  });
});
