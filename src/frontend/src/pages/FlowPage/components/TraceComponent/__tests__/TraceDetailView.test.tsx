import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import useFlowStore from "@/stores/flowStore";
import { TraceDetailView } from "../TraceDetailView";
import type { Trace } from "../types";

let mockTrace: Trace | null = null;
let mockIsLoading = false;

jest.mock("@/controllers/API/queries/traces", () => ({
  useGetTraceQuery: () => ({
    data: mockTrace,
    isLoading: mockIsLoading,
  }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({
    name,
    dataTestId,
    skipFallback,
    ...rest
  }: {
    name: string;
    dataTestId?: string;
    skipFallback?: boolean;
  }) => <span data-testid={dataTestId ?? `icon-${name}`} {...rest} />,
}));

jest.mock("@/components/core/codeTabsComponent", () => ({
  __esModule: true,
  default: ({ code }: { code: string }) => (
    <pre data-testid="code-tab">{code}</pre>
  ),
}));

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div data-testid="loading" />,
}));

jest.mock("../TraceHitlBar", () => ({
  TraceHitlBar: ({ onDecision }: { onDecision?: (a: string) => void }) => (
    <button
      type="button"
      data-testid="hitl-bar"
      onClick={() => onDecision?.("approve")}
    >
      bar
    </button>
  ),
}));

describe("TraceDetailView", () => {
  beforeEach(() => {
    mockTrace = null;
    mockIsLoading = false;
  });

  it("renders a run summary node above the span hierarchy and shows trace input/output when selected", async () => {
    mockTrace = {
      id: "trace-1",
      name: "My Trace",
      status: "ok",
      startTime: "2024-01-01T00:00:00Z",
      endTime: "2024-01-01T00:00:01Z",
      totalLatencyMs: 1234,
      totalTokens: 0,
      totalCost: 0,
      flowId: "flow-1",
      sessionId: "session-1",
      input: { input_value: "hello" },
      output: { result: "world" },
      spans: [
        {
          id: "span-1",
          name: "Child Span",
          type: "llm",
          status: "ok",
          startTime: "2024-01-01T00:00:00Z",
          endTime: "2024-01-01T00:00:01Z",
          latencyMs: 10,
          inputs: {},
          outputs: {},
          children: [],
        },
      ],
    };

    render(<TraceDetailView traceId="trace-1" flowName="Flow" />);

    // Summary node should render as the root.
    expect(screen.getByTestId("span-node-trace-1")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("span-node-trace-1")).getByText("My Trace"),
    ).toBeInTheDocument();

    // Child span should render under it by default.
    expect(screen.getByTestId("span-node-span-1")).toBeInTheDocument();

    // Summary is default-selected; detail shows full input/output.
    await waitFor(() => {
      const codeBlocks = screen.getAllByTestId("code-tab");
      expect(codeBlocks[0]).toHaveTextContent('"input_value": "hello"');
      expect(codeBlocks[1]).toHaveTextContent('"result": "world"');
    });
  });

  it("injects a Human In The Loop node + bar when a request is pending", () => {
    mockTrace = {
      id: "trace-2",
      name: "Paused Trace",
      status: "ok",
      startTime: "2024-01-01T00:00:00Z",
      endTime: "2024-01-01T00:00:01Z",
      totalLatencyMs: 1234,
      totalTokens: 0,
      totalCost: 0,
      flowId: "flow-1",
      sessionId: "session-1",
      input: {},
      output: {},
      spans: [
        {
          id: "span-1",
          name: "Agent",
          type: "agent",
          status: "ok",
          startTime: "2024-01-01T00:00:00Z",
          endTime: "2024-01-01T00:00:01Z",
          latencyMs: 10,
          inputs: {},
          outputs: {},
          children: [],
        },
      ],
    };

    render(
      <TraceDetailView
        traceId="trace-2"
        flowName="Flow"
        hasTrace
        pendingRequest={{
          job_id: "job-1",
          flow_id: "flow-1",
          session_id: "session-1",
          created_at: null,
          request_id: "Agent-oYRYa:job-1",
          kind: "tool_approval",
          prompt: null,
          options: [],
          allowed_decisions: ["approve", "reject"],
        }}
      />,
    );

    // The real components still render...
    expect(screen.getByTestId("span-node-span-1")).toBeInTheDocument();
    // ...plus the injected awaiting HITL node and the resume bar.
    const hitlNode = screen.getByTestId("span-node-hitl-Agent-oYRYa:job-1");
    expect(within(hitlNode).getByText("Human In The Loop")).toBeInTheDocument();
    expect(within(hitlNode).getByText("—")).toBeInTheDocument();
    expect(screen.getByTestId("hitl-bar")).toBeInTheDocument();
  });

  it("lights up components live from build status while the resumed run executes", () => {
    useFlowStore.setState({
      isBuilding: true,
      nodes: [
        { id: "Agent-x", data: { node: { display_name: "Agent" } } },
      ] as never,
      flowBuildStatus: { "Agent-x": { status: "BUILDING" } } as never,
    });
    try {
      mockTrace = {
        id: "trace-4",
        name: "Running Trace",
        status: "ok",
        startTime: "2024-01-01T00:00:00Z",
        endTime: "2024-01-01T00:00:01Z",
        totalLatencyMs: 1234,
        totalTokens: 0,
        totalCost: 0,
        flowId: "flow-1",
        sessionId: "session-1",
        input: {},
        output: {},
        spans: [
          {
            id: "agent-span",
            name: "Agent",
            type: "agent",
            status: "ok",
            startTime: "2024-01-01T00:00:00Z",
            endTime: "2024-01-01T00:00:01Z",
            latencyMs: 10,
            inputs: {},
            outputs: {},
            children: [],
          },
        ],
      };

      render(
        <TraceDetailView
          traceId="trace-4"
          flowName="Flow"
          hasTrace
          pollUpdates
        />,
      );

      // The Agent component reflects the live BUILDING status (running spinner), not the
      // persisted "ok", because the resumed run is still executing it.
      const agentNode = screen.getByTestId("span-node-agent-span");
      expect(
        within(agentNode).getByTestId("flow-log-status-unset"),
      ).toBeInTheDocument();
      // A building node shows no duration (em dash), never a stale "0 ms"/"10 ms".
      expect(within(agentNode).getByText("—")).toBeInTheDocument();
      expect(within(agentNode).queryByText("10 ms")).not.toBeInTheDocument();
    } finally {
      useFlowStore.setState({
        isBuilding: false,
        nodes: [],
        flowBuildStatus: {},
      });
    }
  });

  it("keeps the gate as a resolved step after Approve instead of vanishing", () => {
    mockTrace = {
      id: "trace-5",
      name: "Gated Trace",
      status: "ok",
      startTime: "2024-01-01T00:00:00Z",
      endTime: "2024-01-01T00:00:01Z",
      totalLatencyMs: 1234,
      totalTokens: 0,
      totalCost: 0,
      flowId: "flow-1",
      sessionId: "session-1",
      input: {},
      output: {},
      spans: [],
    };

    render(
      <TraceDetailView
        traceId="trace-5"
        flowName="Flow"
        hasTrace
        pendingRequest={{
          job_id: "job-1",
          flow_id: "flow-1",
          session_id: "session-1",
          created_at: null,
          request_id: "Agent-oYRYa:job-1",
          kind: "tool_approval",
          prompt: null,
          options: [],
          allowed_decisions: ["approve", "reject"],
        }}
      />,
    );

    // Awaiting: plain "Human In The Loop" node.
    expect(
      screen.getByTestId("span-node-hitl-Agent-oYRYa:job-1"),
    ).toBeInTheDocument();

    // Approve → the gate stays as a resolved "— Approved" step, not removed.
    fireEvent.click(screen.getByTestId("hitl-bar"));
    expect(
      screen.getByText(/Human In The Loop — Approved/),
    ).toBeInTheDocument();
  });

  it("recovers selection to the result when the HITL node is resolved away", () => {
    mockTrace = {
      id: "trace-3",
      name: "Resolved Trace",
      status: "ok",
      startTime: "2024-01-01T00:00:00Z",
      endTime: "2024-01-01T00:00:01Z",
      totalLatencyMs: 1234,
      totalTokens: 0,
      totalCost: 0,
      flowId: "flow-1",
      sessionId: "session-1",
      input: { input_value: "hi" },
      output: { result: "done" },
      spans: [],
    };

    const pending = {
      job_id: "job-1",
      flow_id: "flow-1",
      session_id: "session-1",
      created_at: null,
      request_id: "Agent-oYRYa:job-1",
      kind: "tool_approval",
      prompt: null,
      options: [],
      allowed_decisions: ["approve", "reject"],
    };

    const { rerender } = render(
      <TraceDetailView
        traceId="trace-3"
        flowName="Flow"
        hasTrace
        pendingRequest={pending}
      />,
    );
    // Paused: the HITL node is present.
    expect(
      screen.getByTestId("span-node-hitl-Agent-oYRYa:job-1"),
    ).toBeInTheDocument();

    // Resolve away the pending (Approve) — the HITL node disappears and the panel must show the
    // run result, not stay stuck on the gone node.
    rerender(<TraceDetailView traceId="trace-3" flowName="Flow" hasTrace />);
    expect(
      screen.queryByTestId("span-node-hitl-Agent-oYRYa:job-1"),
    ).not.toBeInTheDocument();
    const codeBlocks = screen.getAllByTestId("code-tab");
    expect(codeBlocks[0]).toHaveTextContent('"input_value": "hi"');
    expect(codeBlocks[1]).toHaveTextContent('"result": "done"');
  });
});
