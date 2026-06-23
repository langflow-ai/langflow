import { render, screen } from "@testing-library/react";
import type { InteractiveContent } from "@/types/chat";
import { useHitlStore } from "@/stores/hitlStore";
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
  Popover: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  PopoverAnchor: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  PopoverContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
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
