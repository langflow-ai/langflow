// Tests for the enriched PLAN pane (verification cockpit): the verified-progress
// hero, tree row badges + roll-up, the node-detail stepper / frozen contract /
// roll-up gate / transition palette / links card, and the Item ↔ Implementation
// toggle. All Lothal plan hooks are mocked — these assert the UI wiring, not the
// network.

import { fireEvent, render, screen } from "@testing-library/react";

const noopMutation = () => ({
  mutate: jest.fn(),
  mutateAsync: jest.fn(),
  reset: jest.fn(),
  isPending: false,
  isError: false,
  error: null,
});

const mockUsePlan = jest.fn();
const mockUsePlanNode = jest.fn();
const mockUsePlanTests = jest.fn();
const mockUsePlanNodeEvents = jest.fn();

jest.mock("@/controllers/API/queries/lothal", () => ({
  usePlan: () => mockUsePlan(),
  usePlanNode: (_p: string, nodeId: string | null) => mockUsePlanNode(nodeId),
  usePlanTests: (_p: string, nodeId: string | null) => mockUsePlanTests(nodeId),
  usePlanNodeEvents: () => mockUsePlanNodeEvents(),
  usePlanActivity: () => ({ data: [], isLoading: false, error: null }),
  useCreatePlanNode: () => noopMutation(),
  useApprovePlan: () => noopMutation(),
  useCreatePlanTest: () => noopMutation(),
  useRecordPlanTestRun: () => noopMutation(),
  useMovePlanNode: () => noopMutation(),
  useCreatePlanLink: () => noopMutation(),
  useRatifyPlanNode: () => noopMutation(),
  useTransitionPlanNode: () => noopMutation(),
  useUpdatePlanContract: () => noopMutation(),
  useUpdatePlanCriteria: () => noopMutation(),
}));

import { PlanPane } from "../PlanPane";

const project = {
  id: "p1",
  user_id: "u1",
  name: "Auth Platform",
  phase: "PLAN",
  prd_content: null,
  diagram_json: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const NODES = [
  {
    id: "app1",
    parent_id: null,
    kind: "app",
    state: "in_verification",
    name: "Auth Platform",
    depth: 0,
  },
  {
    id: "cmp1",
    parent_id: "app1",
    kind: "component",
    state: "verified",
    name: "Node Core",
    depth: 1,
  },
  {
    id: "epc1",
    parent_id: "app1",
    kind: "epic",
    state: "ratified",
    name: "Transition guards",
    depth: 1,
  },
];

const LINKS = [
  { id: "l1", source_id: "app1", target_id: "cmp1", link_type: "derives_from" },
];

const DETAILS: Record<string, unknown> = {
  app1: {
    id: "app1",
    project_id: "p1",
    kind: "app",
    state: "in_verification",
    name: "Auth Platform",
    description: "End-to-end authenticated sessions.",
    verification_criteria: [
      "A user can sign in and reach a protected resource",
    ],
    test_methodology: "integration",
    acceptance_criteria: ["No anonymous access to protected routes"],
    frozen_verification_criteria: null,
    verified_at: null,
    contract: {
      version: 2,
      assumptions: ["OIDC identity provider available"],
      guarantees: ["End-to-end authenticated sessions"],
      frozen_assumptions: ["OIDC identity provider available"],
      frozen_guarantees: ["End-to-end authenticated sessions"],
      frozen_at: "2026-01-02T00:00:00Z",
    },
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
};

beforeEach(() => {
  mockUsePlan.mockReturnValue({
    data: { plan_id: "tree1", nodes: NODES, links: LINKS },
    isLoading: false,
    error: null,
  });
  mockUsePlanNode.mockImplementation((nodeId: string | null) => ({
    data: nodeId ? (DETAILS[nodeId] ?? null) : null,
    isLoading: false,
    error: null,
  }));
  mockUsePlanTests.mockReturnValue({ data: [], isLoading: false, error: null });
  mockUsePlanNodeEvents.mockReturnValue({
    data: [],
    isLoading: false,
    error: null,
  });
});

describe("PlanPane — verification cockpit", () => {
  it("renders the verified-progress hero from node states", () => {
    render(<PlanPane project={project as never} />);
    // 1 of 3 nodes verified → 33%.
    expect(screen.getByText("of 3 verified")).toBeInTheDocument();
    expect(screen.getByText("33%")).toBeInTheDocument();
    expect(screen.getByText("Verification tree")).toBeInTheDocument();
  });

  it("shows kind labels and a roll-up fraction on parent rows", () => {
    render(<PlanPane project={project as never} />);
    // Kind abbreviations on the rows.
    expect(screen.getByText("APP")).toBeInTheDocument();
    expect(screen.getByText("CMP")).toBeInTheDocument();
    // The app has 2 children, 1 verified → "1/2" roll-up.
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });

  it("opens a node into the stepper + frozen contract + gate + transitions", () => {
    render(<PlanPane project={project as never} />);
    fireEvent.click(screen.getByText("Auth Platform", { selector: "span" }));

    // State-machine stepper labels ("In verification" also appears in the state
    // chip, so it renders more than once).
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getAllByText("In verification").length).toBeGreaterThan(0);
    // Guard line for the in_verification state.
    expect(screen.getByText(/Guard · Roll-up gate/)).toBeInTheDocument();

    // Frozen contract read view (not editable textareas). The version label
    // appears in both the header sub-line and the contract card.
    expect(screen.getAllByText("Frozen").length).toBeGreaterThan(0);
    expect(screen.getAllByText("contract v2").length).toBeGreaterThan(0);
    expect(
      screen.getByText("End-to-end authenticated sessions"),
    ).toBeInTheDocument();

    // Roll-up gate hero with the children check (1/2 verified → locked).
    expect(screen.getByText("Roll-up gate locked")).toBeInTheDocument();
    expect(screen.getByText("All children verified")).toBeInTheDocument();

    // Transition palette: in_verification → verified (gate-blocked) / failed.
    const verifyBtn = screen.getByRole("button", { name: "Mark verified" });
    expect(verifyBtn).toBeDisabled();
    expect(screen.getByRole("button", { name: "Mark failed" })).toBeEnabled();

    // Typed link surfaced on the node.
    expect(screen.getByText("Dependencies & links")).toBeInTheDocument();
    expect(screen.getAllByText("derives_from").length).toBeGreaterThan(0);
  });

  it("toggles into the Implementation preview", () => {
    render(<PlanPane project={project as never} />);
    fireEvent.click(screen.getByText("Auth Platform", { selector: "span" }));

    // Default is the Item view; switch to Implementation.
    fireEvent.click(screen.getByRole("button", { name: /Implementation/ }));
    expect(screen.getByText(/Preview/)).toBeInTheDocument();
    expect(screen.getByText(/agent\/auth-platform/)).toBeInTheDocument();
    // The build sub-tabs exist.
    expect(screen.getByRole("button", { name: "Diff" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log" })).toBeInTheDocument();
  });

  it("switches to the interactive graph and back via a node click", () => {
    render(<PlanPane project={project as never} />);
    fireEvent.click(screen.getByRole("button", { name: "Graph" }));
    // Legend is present in the graph view.
    expect(screen.getByText("typed peer links · the DAG")).toBeInTheDocument();
  });
});
