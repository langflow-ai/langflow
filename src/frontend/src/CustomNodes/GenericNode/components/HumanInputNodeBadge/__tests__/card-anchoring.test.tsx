/**
 * The decision card must render INSIDE the node subtree, not in a
 * document.body portal. The canvas zoom is a CSS transform on the xyflow viewport; it fires no
 * scroll/resize, so a portaled (floating-ui) card repositions late and visibly lags behind the
 * node. Rendered inline, the card inherits the viewport transform and moves/scales with the node.
 *
 * Uses the REAL popover module (unlike index.test.tsx, which mocks it away) so the
 * portal-vs-inline behavior is what's actually asserted.
 */

import { render } from "@testing-library/react";
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

const content: InteractiveContent = {
  type: "human_input",
  kind: "node_input",
  request_id: "HumanInput-abc:job-1",
  prompt: "Approve?",
  options: [{ action_id: "approve", label: "Approve" }],
  allowed_decisions: ["approve"],
  job_id: "job-1",
};

describe("HumanInputNodeBadge card anchoring", () => {
  afterEach(() => useHitlStore.getState().clear());

  it("should render the open decision card inside the node subtree (not a body portal) so it follows canvas zoom", () => {
    useHitlStore.getState().setPending({ nodeId: "HumanInput-abc", content });

    const { container } = render(
      <HumanInputNodeBadge nodeId="HumanInput-abc" />,
    );

    // The badge auto-opens the card when its node is awaiting input.
    expect(
      container.querySelector('[data-testid="human-input-node-badge"]'),
    ).not.toBeNull();
    // Inline (non-portaled) content is a descendant of the render container; a portaled card
    // would live under document.body instead and lag behind the node on canvas zoom.
    expect(container.querySelector('[data-testid="hitl-card"]')).not.toBeNull();
  });
});
