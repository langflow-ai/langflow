/**
 * Integration test for PR #12575 round 2: drives the REAL ``useAssistantChat``
 * hook with the production SSE sequence and renders the REAL
 * ``AssistantMessageBody`` against the message the hook produces. The
 * existing hook-level tests assert state-only (proposal fields are set),
 * and the existing component-level tests render ``AssistantFlowPreview`` in
 * isolation — but neither catches the gap reported by the user: state is
 * set correctly yet the card never shows up in the panel.
 *
 * The bug repros only when the full pipeline runs together. This test wires
 * both ends so a regression in EITHER the hook contract OR the message-body
 * rendering decision tree surfaces here.
 */
import { act, render, renderHook, screen } from "@testing-library/react";

// react-markdown / remark-gfm are ESM and break Jest's CJS transformer.
jest.mock("react-markdown", () => {
  return function MockMarkdown({ children }: { children: string }) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});
jest.mock("remark-gfm", () => () => {});

jest.mock("../../helpers/chat-markdown", () => ({
  ChatMarkdown: ({ children }: { children: string }) => (
    <div data-testid="chat-markdown">{children}</div>
  ),
}));

jest.mock("@/components/core/codeTabsComponent", () => {
  return function MockCodeTab({ code }: { code: string }) {
    return <div data-testid="code-tab">{code}</div>;
  };
});

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
  useUpdateNodeInternals: () => () => {},
}));

// Sibling components message-body imports — stub each so a render path
// reaching them is observable but doesn't drag heavy deps.
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

const mockPostAssistStream = jest.fn();
jest.mock("@/controllers/API/queries/agentic", () => ({
  postAssistStream: (...args: unknown[]) => mockPostAssistStream(...args),
}));

const mockValidateComponent = jest.fn();
jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({
      mutateAsync: mockValidateComponent,
    }),
  }),
);

const mockAddComponent = jest.fn();
jest.mock("@/hooks/use-add-component", () => ({
  useAddComponent: () => mockAddComponent,
}));

jest.mock("@/hooks/flows/use-save-flow", () => ({
  __esModule: true,
  default: () => jest.fn().mockResolvedValue(undefined),
}));

jest.mock("@/stores/flowsManagerStore", () => {
  const fn = (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "test-flow-id" });
  fn.getState = () => ({ currentFlowId: "test-flow-id" });
  return { __esModule: true, default: fn };
});

const mockSetNodes = jest.fn();
const mockSetEdges = jest.fn();
const mockPaste = jest.fn();
jest.mock("@/stores/flowStore", () => {
  const state = {
    setNodes: (...args: unknown[]) => mockSetNodes(...args),
    setEdges: (...args: unknown[]) => mockSetEdges(...args),
    paste: (...args: unknown[]) => mockPaste(...args),
    get nodes() {
      return [];
    },
    get edges() {
      return [];
    },
  };
  const fn = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  fn.getState = () => state;
  return { __esModule: true, default: fn };
});

jest.mock("short-unique-id", () => {
  let counter = 0;
  return class ShortUniqueId {
    randomUUID() {
      counter += 1;
      return `mock-uid-${counter}`;
    }
  };
});

import { AssistantMessageBody } from "../assistant-message-body";
import { useAssistantChat } from "../../hooks/use-assistant-chat";

const TEST_MODEL = {
  id: "openai/gpt-4o-mini",
  name: "gpt-4o-mini",
  provider: "openai",
  displayName: "GPT-4o mini",
};

const SAMPLE_FLOW = {
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

describe("Proposal pipeline integration (PR #12575 round 2)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_render_AssistantFlowPreview_card_after_full_proposal_SSE_sequence", async () => {
    // Replay the EXACT production SSE sequence captured in
    // PR-12575-retest2-sse-gpt4o.txt:
    //   1. progress: generating_flow
    //   2. progress: generation_complete
    //   3. flow_update: set_flow (NO auto_apply)
    //   4. progress: flow_proposal_ready
    //   5. complete: success=true, has_flow=true, continuation_expected=false
    mockPostAssistStream.mockImplementation(
      async (_request: unknown, callbacks: Record<string, Function>) => {
        callbacks.onProgress({
          event: "progress",
          step: "generating_flow",
          attempt: 1,
          max_attempts: 4,
          message: "Working on the flow...",
        });
        callbacks.onProgress({
          event: "progress",
          step: "generation_complete",
          attempt: 1,
          max_attempts: 4,
          message: "Response ready",
        });
        callbacks.onFlowUpdate({
          event: "flow_update",
          action: "set_flow",
          flow: SAMPLE_FLOW,
        });
        callbacks.onProgress({
          event: "progress",
          step: "flow_proposal_ready",
          attempt: 1,
          max_attempts: 4,
          message: "Flow ready — review and continue",
        });
        callbacks.onComplete({
          event: "complete",
          data: {
            result:
              "Built a Chat Flow with nodes: ChatInput -> OpenAIModel -> ChatOutput, configured to use the OpenAI model `gpt-4o-mini`.",
            success: true,
            has_flow: true,
            continuation_expected: false,
          },
        });
      },
    );

    const { result } = renderHook(() => useAssistantChat());

    await act(async () => {
      await result.current.handleSend(
        "Build a chat flow with ChatInput → OpenAI → ChatOutput",
        TEST_MODEL,
      );
    });

    // Sanity: state was set correctly (the existing tests already cover
    // this, repeated here so a failure points at hook OR render).
    const msg = result.current.messages[1];
    expect(msg.flowProposalStatus).toBe("pending");
    expect(msg.pendingFlowProposal).toBeDefined();
    expect(mockSetNodes).not.toHaveBeenCalled();
    expect(mockSetEdges).not.toHaveBeenCalled();

    // The actual contract: feed the produced message back into the real
    // body — the user's eyes-on-screen check. The card MUST be reachable.
    render(<AssistantMessageBody message={msg} isGeneratingCode={false} />);

    expect(screen.getByTestId("assistant-flow-add-button")).toBeInTheDocument();
    expect(
      screen.getByTestId("assistant-flow-dismiss-button"),
    ).toBeInTheDocument();
    // None of the alternate render paths should have hijacked the render.
    expect(screen.queryByTestId("loading-state-mock")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("validation-failed-mock"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("component-result-mock"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("plan-card-mock")).not.toBeInTheDocument();
    expect(screen.queryByTestId("flow-edit-mock")).not.toBeInTheDocument();
  });
});
