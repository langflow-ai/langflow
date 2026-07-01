import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Project } from "@/controllers/API/queries/lothal";

// react-markdown / remark-gfm are ESM; mock them (repo convention) — the PrdPane
// renders the PRD markdown, and we assert the spec text is handed through.
jest.mock("react-markdown", () => ({
  __esModule: true,
  default: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="prd-markdown">{children}</div>
  ),
}));
jest.mock("remark-gfm", () => ({ __esModule: true, default: () => {} }));

const mockUpdateMutate = jest.fn();
const mockApproveMutate = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useUpdatePrd: () => ({ mutateAsync: mockUpdateMutate, isPending: false }),
  useApprovePrd: () => ({ mutateAsync: mockApproveMutate, isPending: false }),
}));

import { PrdPane } from "../PrdPane";

const project = (over: Partial<Project> = {}): Project =>
  ({
    id: "p1",
    user_id: "u1",
    name: "Tide Tracker",
    phase: "CLARIFICATION",
    prd_content: null,
    diagram_json: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...over,
  }) as Project;

beforeEach(() => {
  jest.clearAllMocks();
  mockUpdateMutate.mockResolvedValue({ content: "ok" });
  mockApproveMutate.mockResolvedValue({ phase: "ARCHITECTURE" });
});

describe("PrdPane", () => {
  it("shows the clarifying placeholder while no PRD is drafted yet", () => {
    render(<PrdPane project={project()} />);
    expect(screen.getByText("Clarifying your idea…")).toBeInTheDocument();
    // Nothing to approve yet.
    expect(
      screen.queryByRole("button", { name: /Approve/ }),
    ).not.toBeInTheDocument();
  });

  it("renders the drafted PRD on the main page with an approve gate", () => {
    render(
      <PrdPane
        project={project({ prd_content: "# Spec\n\nA tide tracker." })}
      />,
    );
    expect(screen.getByTestId("prd-markdown")).toHaveTextContent(
      "A tide tracker.",
    );
    expect(
      screen.getByRole("button", { name: "Approve & design architecture" }),
    ).toBeInTheDocument();
  });

  it("approves the PRD, advancing to the architecture stage", async () => {
    render(
      <PrdPane
        project={project({ prd_content: "# Spec\n\nA tide tracker." })}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Approve & design architecture" }),
    );
    await waitFor(() => expect(mockApproveMutate).toHaveBeenCalledTimes(1));
  });

  it("edits the spec: Edit → textarea → Save persists the change", async () => {
    render(
      <PrdPane project={project({ prd_content: "# Spec\n\nOld body." })} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    const box = screen.getByRole("textbox");
    fireEvent.change(box, { target: { value: "# Spec\n\nNew body." } });
    fireEvent.click(screen.getByRole("button", { name: "Save spec" }));
    await waitFor(() =>
      expect(mockUpdateMutate).toHaveBeenCalledWith("# Spec\n\nNew body."),
    );
  });

  it("is read-only once the project has advanced past clarification", () => {
    render(
      <PrdPane
        project={project({
          phase: "ARCHITECTURE",
          prd_content: "# Spec\n\nA tide tracker.",
        })}
      />,
    );
    // The spec still renders, but no edit/approve controls when browsing back.
    expect(screen.getByTestId("prd-markdown")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Edit" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Approve/ }),
    ).not.toBeInTheDocument();
  });
});
