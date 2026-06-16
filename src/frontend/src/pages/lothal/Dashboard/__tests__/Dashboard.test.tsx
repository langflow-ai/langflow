import { fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const mockUseProjects = jest.fn();
const mockCreateMutate = jest.fn();
const mockDeleteMutate = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useProjects: () => mockUseProjects(),
  useCreateProject: () => ({ mutate: mockCreateMutate, isPending: false }),
  useDeleteProject: () => ({ mutate: mockDeleteMutate }),
}));

import { LOTHAL_VERSION } from "../../components";
import Dashboard from "../index";

// Fixed "now" used across relativeTime bucket tests: 2026-06-01T12:00:00Z.
// Each fixture's updated_at is computed relative to this so the bucket
// is unambiguous (staying well away from bucket edges avoids off-by-one
// flakiness in the test runner).
const NOW_ISO = "2026-06-01T12:00:00Z";
const NOW_MS = new Date(NOW_ISO).getTime();

const project = {
  id: "p1",
  user_id: "u1",
  name: "Demo",
  phase: "DIAGRAM_REFINEMENT",
  prd_content: null,
  diagram_mmd: null,
  diagram_layout: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("Lothal Dashboard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows the empty state when there are no projects", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);
    expect(screen.getByText("No projects yet")).toBeInTheDocument();
  });

  it("renders the product version badge from the single LOTHAL_VERSION source", () => {
    // Drift guard: the TopBar badge must echo the constant, not a hardcode.
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);
    expect(screen.getByText(`v${LOTHAL_VERSION}`)).toBeInTheDocument();
  });

  it("renders a card per project with its name and status verb", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    render(<Dashboard />);
    expect(screen.getByText("Demo")).toBeInTheDocument();
    // StatusDot verb for the phase (DIAGRAM_REFINEMENT → "refining").
    expect(screen.getByText("refining")).toBeInTheDocument();
  });

  it("shows the project counts beside the Projects heading", () => {
    mockUseProjects.mockReturnValue({
      data: [project, { ...project, id: "p2", phase: "DONE" }],
      isLoading: false,
    });
    render(<Dashboard />);
    // All · 2 / In progress · 1 (the refinement one) / Delivered · 1.
    expect(screen.getByText("All · 2")).toBeInTheDocument();
    expect(screen.getByText("In progress · 1")).toBeInTheDocument();
    expect(screen.getByText("Delivered · 1")).toBeInTheDocument();
  });

  it("confirms before deleting and only deletes when confirmed", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<Dashboard />);

    const deleteButton = screen.getByRole("button", { name: "Delete Demo" });

    fireEvent.click(deleteButton);
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(mockDeleteMutate).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    fireEvent.click(deleteButton);
    expect(mockDeleteMutate).toHaveBeenCalledWith("p1");

    confirmSpy.mockRestore();
  });

  it("opens the card on Enter/Space from the card itself", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    render(<Dashboard />);
    const card = screen
      .getByText("Demo")
      .closest('[role="button"]') as HTMLElement;

    fireEvent.keyDown(card, { key: "Enter" });
    expect(mockNavigate).toHaveBeenCalledWith("/lothal/p1");

    mockNavigate.mockClear();
    fireEvent.keyDown(card, { key: " " });
    expect(mockNavigate).toHaveBeenCalledWith("/lothal/p1");
  });

  it("does not open the card when the delete button receives Enter/Space", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    render(<Dashboard />);
    const deleteButton = screen.getByRole("button", { name: "Delete Demo" });

    // Key events bubble to the card; the card must ignore those from a nested
    // control and stay closed (the delete itself runs on the button's own click).
    fireEvent.keyDown(deleteButton, { key: "Enter" });
    fireEvent.keyDown(deleteButton, { key: " " });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("creates a project from the modal with the trimmed name", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);

    // Open the modal (several "New project" affordances; the first opens it).
    fireEvent.click(screen.getAllByRole("button", { name: "New project" })[0]);

    const input = screen.getByLabelText("Project name");
    fireEvent.change(input, { target: { value: "  Tide Tracker  " } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(mockCreateMutate).toHaveBeenCalledWith(
      "Tide Tracker",
      expect.any(Object),
    );
  });

  // --- Regression guards (from the code review) ----------------------------
  // Each of these reproduced a real bug; the source is now fixed, so they are
  // plain passing tests guarding the fix.

  it("shows an error state — not the empty state — when the project list fails to load", () => {
    // Input: the list query failed (backend 500 / expired session / network drop).
    mockUseProjects.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch: jest.fn(),
    });
    render(<Dashboard />);
    // Expected: a user with real projects is NOT told they have none...
    expect(screen.queryByText("No projects yet")).not.toBeInTheDocument();
    // ...and the error UI with a retry affordance is shown instead.
    expect(screen.getByText("Couldn’t load your projects")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
  });

  it("opens the new-project modal when the advertised 'N' shortcut is pressed", () => {
    // Input: the dashboard advertises an "N to start" shortcut.
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);
    expect(screen.queryByLabelText("Project name")).not.toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "n" });
    // Expected: the modal opens.
    expect(screen.getByLabelText("Project name")).toBeInTheDocument();
  });

  it("ignores the 'N' shortcut when a modifier is held (leaves browser shortcuts alone)", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);
    fireEvent.keyDown(document.body, { key: "n", metaKey: true });
    fireEvent.keyDown(document.body, { key: "n", ctrlKey: true });
    // Expected: Cmd/Ctrl+N is not hijacked, so the modal stays closed.
    expect(screen.queryByLabelText("Project name")).not.toBeInTheDocument();
  });

  it("ignores the 'N' shortcut while typing in the project-name field", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);
    fireEvent.click(screen.getAllByRole("button", { name: "New project" })[0]);
    const input = screen.getByLabelText("Project name");
    // Typing 'n' into the field must not toggle/disturb the open modal.
    fireEvent.keyDown(input, { key: "n" });
    expect(screen.getByLabelText("Project name")).toBeInTheDocument();
  });

  it("surfaces an error when creating a project fails", () => {
    // Input: the create POST fails (the mutation invokes its onError callback).
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    mockCreateMutate.mockImplementation((_name, opts) =>
      opts?.onError?.(new Error("create failed")),
    );
    render(<Dashboard />);
    fireEvent.click(screen.getAllByRole("button", { name: "New project" })[0]);
    fireEvent.change(screen.getByLabelText("Project name"), {
      target: { value: "Tide Tracker" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    // Expected: the user is told the create failed (an alert surfaces).
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  // --- relativeTime bucket tests -------------------------------------------
  // These pin Date.now() to NOW_MS so bucket membership is deterministic.

  describe("relativeTime buckets", () => {
    beforeEach(() => {
      jest.useFakeTimers();
      jest.setSystemTime(NOW_MS);
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    function renderWithTimestamp(updatedAt: string) {
      mockUseProjects.mockReturnValue({
        data: [{ ...project, updated_at: updatedAt }],
        isLoading: false,
      });
      render(<Dashboard />);
    }

    it("shows 'just now' when updated less than one minute ago", () => {
      // 30 seconds before NOW — comfortably inside the < 1 min bucket.
      const ts = new Date(NOW_MS - 30_000).toISOString();
      renderWithTimestamp(ts);
      expect(screen.getByText("just now")).toBeInTheDocument();
    });

    it("shows 'N minutes ago' when updated 1–59 minutes ago (singular)", () => {
      // Exactly 1 minute ago.
      const ts = new Date(NOW_MS - 60_000).toISOString();
      renderWithTimestamp(ts);
      expect(screen.getByText("1 minute ago")).toBeInTheDocument();
    });

    it("shows 'N minutes ago' when updated 1–59 minutes ago (plural)", () => {
      // 5 minutes ago — well inside the minutes bucket.
      const ts = new Date(NOW_MS - 5 * 60_000).toISOString();
      renderWithTimestamp(ts);
      expect(screen.getByText("5 minutes ago")).toBeInTheDocument();
    });

    it("shows 'N hours ago' when updated 1–23 hours ago (singular)", () => {
      // Exactly 1 hour ago.
      const ts = new Date(NOW_MS - 60 * 60_000).toISOString();
      renderWithTimestamp(ts);
      expect(screen.getByText("1 hour ago")).toBeInTheDocument();
    });

    it("shows 'N hours ago' when updated 1–23 hours ago (plural)", () => {
      // 3 hours ago — well inside the hours bucket.
      const ts = new Date(NOW_MS - 3 * 60 * 60_000).toISOString();
      renderWithTimestamp(ts);
      expect(screen.getByText("3 hours ago")).toBeInTheDocument();
    });

    it("shows 'yesterday' when updated exactly one day ago", () => {
      // 26 hours ago — day===1, safely away from the 24 h and 48 h boundaries.
      const ts = new Date(NOW_MS - 26 * 60 * 60_000).toISOString();
      renderWithTimestamp(ts);
      expect(screen.getByText("yesterday")).toBeInTheDocument();
    });

    it("shows 'N days ago' when updated 2–6 days ago", () => {
      // 3 days ago — squarely in the days bucket (day===3).
      const ts = new Date(NOW_MS - 3 * 24 * 60 * 60_000).toISOString();
      renderWithTimestamp(ts);
      expect(screen.getByText("3 days ago")).toBeInTheDocument();
    });

    it("shows an absolute date when updated 7 or more days ago", () => {
      // 10 days before NOW_MS → 2026-05-22 — well past the 7-day cutoff.
      const tenDaysAgo = new Date(NOW_MS - 10 * 24 * 60 * 60_000);
      const ts = tenDaysAgo.toISOString();
      renderWithTimestamp(ts);
      // The source calls toLocaleDateString with { month:'short', day:'numeric',
      // year:'numeric' }. We assert the year appears rather than hardcoding a
      // locale-specific month/day string so the test stays locale-agnostic.
      expect(
        screen.getByText((text) => text.includes("2026")),
      ).toBeInTheDocument();
      // And it must NOT be a relative-time string.
      expect(
        screen.queryByText(/ago|just now|yesterday/i),
      ).not.toBeInTheDocument();
    });

    it("appends 'Z' to bare UTC timestamps (no TZ offset) before computing the diff", () => {
      // The API often sends naive timestamps without a trailing Z.  The
      // toDate() helper must treat them as UTC so the browser's local offset
      // doesn't corrupt the bucket.  We pass the bare form and assert the
      // bucket is correct under the controlled clock.
      // 5 minutes ago as a bare ISO string (no Z / offset).
      const bareTs = new Date(NOW_MS - 5 * 60_000)
        .toISOString()
        .replace("Z", "");
      renderWithTimestamp(bareTs);
      expect(screen.getByText("5 minutes ago")).toBeInTheDocument();
    });
  });

  // --- Settings navigation --------------------------------------------------

  it("navigates to /lothal/settings when the TopBar 'Settings' button is clicked", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);
    // The TopBar right slot contains two Settings affordances: a text "Settings"
    // button and an avatar button (which also resolves to name "Settings" when
    // there's no logged-in username).  Both call navigate('/lothal/settings').
    // Click the first one — the text button — and assert the route.
    const settingsBtns = screen.getAllByRole("button", { name: "Settings" });
    expect(settingsBtns.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(settingsBtns[0]);
    expect(mockNavigate).toHaveBeenCalledWith("/lothal/settings");
  });

  // --- Voice guard ----------------------------------------------------------

  it("renders no nautical / dockyard wording in the visible text", () => {
    mockUseProjects.mockReturnValue({
      data: [
        { ...project, id: "p1", phase: "CLARIFICATION" },
        { ...project, id: "p2", phase: "DONE" },
      ],
      isLoading: false,
    });
    render(<Dashboard />);
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/harbor|vessel|dockyard|keel|drydock/i);
  });
});
