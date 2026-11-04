import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { FlowInsightsContent } from "../FlowInsightsContent";

// ── query hooks ────────────────────────────────────────────────────────────
let mockIsLoading = true;
let mockTraces: unknown[] = [];

jest.mock("@/controllers/API/queries/traces", () => ({
  useDeleteTracesMutation: () => ({ mutate: jest.fn() }),
  useGetTracesQuery: () => ({
    data: { traces: mockTraces, total: mockTraces.length, pages: 1 },
    isLoading: mockIsLoading,
    refetch: jest.fn(),
  }),
}));

jest.mock(
  "@/controllers/API/queries/workflows/use-get-pending-workflows",
  () => ({
    useGetPendingWorkflows: () => ({ data: [] }),
  }),
);

// ── stores ─────────────────────────────────────────────────────────────────
jest.mock("@/stores/flowsManagerStore", () => {
  const fn = (
    sel: (s: {
      currentFlowId: string;
      currentFlow: null;
      getFlowById: () => null;
    }) => unknown,
  ) =>
    sel({
      currentFlowId: "flow-1",
      currentFlow: null,
      getFlowById: () => null,
    });
  fn.getState = () => ({ currentFlowId: "flow-1" });
  return { __esModule: true, default: fn };
});

jest.mock("@/stores/alertStore", () => {
  const fn = (
    sel: (s: {
      setSuccessData: () => void;
      setErrorData: () => void;
    }) => unknown,
  ) => sel({ setSuccessData: jest.fn(), setErrorData: jest.fn() });
  return { __esModule: true, default: fn };
});

// ── heavy / icon dependencies ───────────────────────────────────────────────
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent",
  () => ({
    __esModule: true,
    default: () => <div data-testid="trace-table" />,
  }),
);

jest.mock("@/components/common/paginatorComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="paginator" />,
}));

jest.mock("../TraceDetailView", () => ({
  TraceDetailView: () => <div data-testid="trace-detail-view" />,
}));

jest.mock("../DateRangePopover", () => ({
  DateRangePopover: () => <div data-testid="date-range-popover" />,
}));

// ── helpers ─────────────────────────────────────────────────────────────────
function renderContent() {
  return render(
    <MemoryRouter>
      <FlowInsightsContent flowId="flow-1" />
    </MemoryRouter>,
  );
}

// ── tests ────────────────────────────────────────────────────────────────────
describe("FlowInsightsContent — skeleton loading state", () => {
  beforeEach(() => {
    mockIsLoading = true;
    mockTraces = [];
  });

  it("renders the skeleton placeholder when loading with no rows", () => {
    renderContent();
    expect(screen.getByTestId("flow-activity-skeleton")).toBeInTheDocument();
  });

  it("renders exactly 6 skeleton rows", () => {
    renderContent();
    const skeleton = screen.getByTestId("flow-activity-skeleton");
    expect(skeleton.children).toHaveLength(6);
  });

  it("does not render the trace table while skeleton is shown", () => {
    renderContent();
    expect(screen.queryByTestId("trace-table")).not.toBeInTheDocument();
  });

  it("hides skeleton and shows table once data is loaded", () => {
    mockIsLoading = false;
    mockTraces = [
      {
        id: "t1",
        name: "Run 1",
        status: "ok",
        startTime: "2024-01-01T00:00:00Z",
        totalLatencyMs: 100,
        totalTokens: 0,
        totalCost: 0,
        flowId: "flow-1",
        sessionId: "s1",
      },
    ];

    renderContent();

    expect(
      screen.queryByTestId("flow-activity-skeleton"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("trace-table")).toBeInTheDocument();
  });

  it("hides skeleton during background refresh when rows are already present", () => {
    mockIsLoading = true;
    mockTraces = [
      {
        id: "t1",
        name: "Run 1",
        status: "ok",
        startTime: "2024-01-01T00:00:00Z",
        totalLatencyMs: 100,
        totalTokens: 0,
        totalCost: 0,
        flowId: "flow-1",
        sessionId: "s1",
      },
    ];

    renderContent();

    expect(
      screen.queryByTestId("flow-activity-skeleton"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("trace-table")).toBeInTheDocument();
  });
});
