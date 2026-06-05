import { fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

const mockUseProjects = jest.fn();
const mockCreateMutate = jest.fn();
const mockDeleteMutate = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useProjects: () => mockUseProjects(),
  useCreateProject: () => ({ mutate: mockCreateMutate }),
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

  it("shows the empty state when there are no projects", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Dashboard />);
    expect(
      screen.getByText("No projects yet. Create one to get started."),
    ).toBeInTheDocument();
  });

  it("renders a card per project using the shared phase label", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    render(<Dashboard />);
    expect(screen.getByText("Demo")).toBeInTheDocument();
    // Shared constant resolves to "Refining Diagram" (not the old "Refining").
    expect(screen.getByText("Refining Diagram")).toBeInTheDocument();
  });

  it("confirms before deleting and only deletes when confirmed", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<Dashboard />);

    const deleteButton = screen
      .getByTestId("icon-Trash2")
      .closest("button") as HTMLButtonElement;

    fireEvent.click(deleteButton);
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(mockDeleteMutate).not.toHaveBeenCalled();

    confirmSpy.mockReturnValue(true);
    fireEvent.click(deleteButton);
    expect(mockDeleteMutate).toHaveBeenCalledWith("p1");

    confirmSpy.mockRestore();
  });
});
