import { render, screen, waitFor, within } from "@testing-library/react";
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
});
