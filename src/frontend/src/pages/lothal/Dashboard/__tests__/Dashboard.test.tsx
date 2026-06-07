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

import Dashboard from "../index";

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

  it("shows the dockyard empty state when there are no projects", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);
    expect(screen.getByText("No vessels in the harbor")).toBeInTheDocument();
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

  it("shows an error state — not the empty 'harbor' — when the project list fails to load", () => {
    // Input: the list query failed (backend 500 / expired session / network drop).
    mockUseProjects.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });
    render(<Dashboard />);
    // Expected: a user with real projects is NOT told they have none.
    expect(
      screen.queryByText("No vessels in the harbor"),
    ).not.toBeInTheDocument();
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
});
