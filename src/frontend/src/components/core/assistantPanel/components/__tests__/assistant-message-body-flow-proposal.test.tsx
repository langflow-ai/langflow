import { render, screen } from "@testing-library/react";

// react-markdown / remark-gfm are ESM and break Jest's CJS transformer.
// AssistantMessageBody imports them at the top of the file; stub them.
jest.mock("react-markdown", () => {
  return function MockMarkdown({ children }: { children: string }) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});
jest.mock("remark-gfm", () => () => {});

// ChatMarkdown helper also pulls in react-markdown — mock it to a passthrough
// so we can still see the assistant's text content in the rendered output.
jest.mock("../../helpers/chat-markdown", () => ({
  ChatMarkdown: ({ children }: { children: string }) => (
    <div data-testid="chat-markdown">{children}</div>
  ),
}));

// codeTabsComponent transitively pulls react-syntax-highlighter which is ESM.
// AssistantMessageBody imports SimplifiedCodeTabComponent at module load,
// so we stub it before the body itself is required.
jest.mock("@/components/core/codeTabsComponent", () => {
  return function MockCodeTab({ code }: { code: string }) {
    return <div data-testid="code-tab">{code}</div>;
  };
});

// Sibling components that AssistantMessageBody imports — none of them
// are exercised by this render path (proposal-card branch), but they
// transitively drag heavy deps. Stub each with a label so we can
// confirm they did NOT render.
jest.mock("../assistant-component-result", () => ({
  AssistantComponentResult: () => <div data-testid="component-result-mock" />,
}));
jest.mock("../assistant-file-card", () => ({
  AssistantFileCard: () => <div data-testid="file-card-mock" />,
}));
jest.mock("../assistant-flow-edit-card", () => ({
  FlowEditCarousel: () => <div data-testid="flow-edit-mock" />,
}));
jest.mock("../assistant-loading-state", () => ({
  AssistantLoadingState: () => <div data-testid="loading-state-mock" />,
}));
jest.mock("../assistant-plan-card", () => ({
  AssistantPlanCard: () => <div data-testid="plan-card-mock" />,
}));
jest.mock("../assistant-validation-failed", () => ({
  AssistantValidationFailed: () => <div data-testid="validation-failed-mock" />,
}));

// AssistantFlowPreview renders a mini ReactFlow canvas; mock the heavy
// internals — we only care that the preview surface is in the DOM.
jest.mock("@xyflow/react", () => ({
  __esModule: true,
  ReactFlow: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="react-flow-mock">{children}</div>
  ),
  ReactFlowProvider: ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  ),
  Background: () => null,
}));

import type { AssistantMessage } from "../../assistant-panel.types";
import { AssistantMessageBody } from "../assistant-message-body";

const mockPaste = jest.fn();
jest.mock("@/stores/flowStore", () => {
  const state = { paste: (...args: unknown[]) => mockPaste(...args) };
  const fn = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  fn.getState = () => state;
  return { __esModule: true, default: fn };
});

const SAMPLE_PROPOSAL_FLOW = {
  name: "Chat Flow",
  data: {
    nodes: [
      {
        id: "ChatInput-x",
        position: { x: 0, y: 0 },
        data: { type: "ChatInput" },
      },
      {
        id: "OpenAIModel-y",
        position: { x: 600, y: 0 },
        data: { type: "OpenAIModel" },
      },
      {
        id: "ChatOutput-z",
        position: { x: 1200, y: 0 },
        data: { type: "ChatOutput" },
      },
    ],
    edges: [
      { id: "e1", source: "ChatInput-x", target: "OpenAIModel-y" },
      { id: "e2", source: "OpenAIModel-y", target: "ChatOutput-z" },
    ],
  },
};

/**
 * Build the exact message shape that ``use-assistant-chat`` produces after
 * the proposal-mode SSE sequence drains: ``set_flow`` (no auto_apply) →
 * ``progress flow_proposal_ready`` → ``complete``. Both the proposal fields
 * and the terminal-completion fields (status, content, result) live on the
 * same message — the production bug from PR #12575 round 2 surfaced because
 * the render path was not reaching the proposal-card branch in this state.
 */
function buildProposalMessage(): AssistantMessage {
  return {
    id: "msg-1",
    role: "assistant",
    content:
      "Built a Chat Flow with nodes: ChatInput -> OpenAIModel -> ChatOutput.",
    timestamp: new Date(),
    status: "complete",
    progress: {
      step: "flow_proposal_ready",
      attempt: 1,
      maxAttempts: 4,
      message: "Flow ready — review and continue",
    },
    continuationExpected: false,
    result: {
      content: "Built a Chat Flow...",
      validated: undefined,
      hasFlow: true,
    },
    pendingFlowProposal: {
      flow: SAMPLE_PROPOSAL_FLOW as unknown as Record<string, unknown>,
      name: "Chat Flow",
      nodeCount: 3,
      edgeCount: 2,
      tailUpdates: [],
    },
    flowProposalStatus: "pending",
  };
}

describe("AssistantMessageBody — proposal-mode render (PR #12575 round 2)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_render_AssistantFlowPreview_card_when_message_has_pending_flow_proposal_after_complete", () => {
    // Reproduces the exact production scenario reported in PR #12575
    // round 2: the user submits "Build a chat flow with X -> Y -> Z",
    // the backend emits proposal-mode events (set_flow without
    // auto_apply, then flow_proposal_ready, then complete), but the
    // user sees only the markdown text and no Apply/Dismiss card.
    render(
      <AssistantMessageBody
        message={buildProposalMessage()}
        isGeneratingCode={false}
      />,
    );

    // The primary Apply button is the contract for the proposal card.
    // If the card is rendered, this testid is reachable.
    expect(screen.getByTestId("assistant-flow-add-button")).toBeInTheDocument();
    expect(
      screen.getByTestId("assistant-flow-dismiss-button"),
    ).toBeInTheDocument();
  });

  // Variant: the message also has ``flowPreview`` set from a prior
  // legacy ``flow_preview`` event. The proposal-card branch must still
  // win over the legacy applied-state branch — otherwise the user sees
  // a muted ``flowPreview`` card with no actions and loses the Apply
  // affordance for the current proposal.
  it("should_prefer_pending_proposal_card_over_legacy_flowPreview_branch", () => {
    const msg: AssistantMessage = {
      ...buildProposalMessage(),
      flowPreview: {
        flow: SAMPLE_PROPOSAL_FLOW as unknown as Record<string, unknown>,
        name: "Chat Flow",
        nodeCount: 3,
        edgeCount: 2,
        graph: "",
      },
    };
    render(<AssistantMessageBody message={msg} isGeneratingCode={false} />);

    expect(screen.getByTestId("assistant-flow-add-button")).toBeInTheDocument();
  });
});
