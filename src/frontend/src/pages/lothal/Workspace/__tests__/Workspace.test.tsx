import { fireEvent, render, screen, waitFor } from "@testing-library/react";

// jsdom has no scrollIntoView; the chat panel calls it on every message change.
Element.prototype.scrollIntoView = jest.fn();

const mockNavigate = jest.fn();
let mockParams: { projectId?: string } = { projectId: "p1" };
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => mockParams,
}));

const mockUseProjects = jest.fn();
const mockUseMessages = jest.fn();
const mockUseDiagram = jest.fn();
const mockSendMutate = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useProjects: () => mockUseProjects(),
  useMessages: () => mockUseMessages(),
  useDiagram: () => mockUseDiagram(),
  useSendMessage: () => ({ mutateAsync: mockSendMutate, isPending: false }),
}));

import Workspace from "../index";

const project = {
  id: "p1",
  user_id: "u1",
  name: "Tide Tracker",
  phase: "CLARIFICATION",
  prd_content: null,
  diagram_mmd: null,
  diagram_layout: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const msg = (over: Partial<Record<string, unknown>>) => ({
  id: "m1",
  project_id: "p1",
  role: "ASSISTANT",
  content: "",
  suggestions: [],
  phase: "CLARIFICATION",
  created_at: "2026-01-01T00:00:00Z",
  ...over,
});

// The shape an axios 501 takes; the chat keys its NotReady state off it.
const error501 = {
  response: {
    status: 501,
    data: {
      detail: "Listing messages is not implemented yet.",
      status: "not_implemented",
    },
  },
};

describe("Lothal Workspace", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockParams = { projectId: "p1" };
    mockSendMutate.mockResolvedValue(msg({ id: "reply", content: "ok" }));
    // Default: messages load fine and empty.
    mockUseMessages.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    // Default: the diagram query is idle (these tests use a CLARIFICATION
    // project, so the canvas shows its placeholder and never reads this).
    mockUseDiagram.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: undefined,
    });
  });

  it("shows a themed loading state while projects load", () => {
    mockUseProjects.mockReturnValue({ data: undefined, isLoading: true });
    render(<Workspace />);
    expect(screen.getByText("Opening the workshop…")).toBeInTheDocument();
  });

  it("shows a not-found state when no project matches the id", () => {
    mockUseProjects.mockReturnValue({ data: [], isLoading: false });
    render(<Workspace />);
    expect(screen.getByText("Project not found")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to the harbor" }));
    expect(mockNavigate).toHaveBeenCalledWith("/lothal");
  });

  it("renders the shell — name, phase stepper, and status verb", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    render(<Workspace />);
    expect(screen.getByText("Tide Tracker")).toBeInTheDocument();
    // PhaseStepper label + StatusDot verb for CLARIFICATION.
    expect(screen.getByText("Clarify")).toBeInTheDocument();
    expect(screen.getByText("clarifying")).toBeInTheDocument();
  });

  it("shows NotReady (not an error) when the messages endpoint 501s", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    mockUseMessages.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: error501,
    });
    render(<Workspace />);
    expect(
      screen.getByText("The conversation isn't live yet"),
    ).toBeInTheDocument();
    // The 501's human detail is surfaced through NotReady.
    expect(
      screen.getByText("Listing messages is not implemented yet."),
    ).toBeInTheDocument();
  });

  it("shows the empty-conversation prompt (no scripted welcome) when live and empty", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    render(<Workspace />);
    expect(screen.getByText("Start the conversation")).toBeInTheDocument();
    // The input dock is always available.
    expect(screen.getByLabelText("Message")).toBeInTheDocument();
  });

  it("renders messages in order with a transition block at a phase boundary", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    mockUseMessages.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        msg({
          id: "m1",
          role: "USER",
          content: "Build a tide app",
          phase: "CLARIFICATION",
        }),
        msg({
          id: "m2",
          role: "ASSISTANT",
          content: "Who is it for?",
          phase: "CLARIFICATION",
        }),
        msg({
          id: "m3",
          role: "ASSISTANT",
          content: "Sketching now",
          phase: "DIAGRAM_GENERATION",
        }),
      ],
    });
    render(<Workspace />);
    expect(screen.getByText("Build a tide app")).toBeInTheDocument();
    expect(screen.getByText("Who is it for?")).toBeInTheDocument();
    expect(
      screen.getByText("Requirements clear — sketching the diagram"),
    ).toBeInTheDocument();
  });

  it("renders suggestion chips only on the latest clarification reply and sends on pick", () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    mockUseMessages.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        msg({
          id: "m1",
          role: "ASSISTANT",
          content: "Who is it for?",
          suggestions: ["Casual", "Serious"],
        }),
      ],
    });
    render(<Workspace />);
    fireEvent.click(screen.getByRole("button", { name: "Casual" }));
    expect(mockSendMutate).toHaveBeenCalledWith("Casual");
  });

  it("sends a typed message and clears the input", async () => {
    mockUseProjects.mockReturnValue({ data: [project], isLoading: false });
    render(<Workspace />);
    const input = screen.getByLabelText("Message") as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: "A tide app" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(mockSendMutate).toHaveBeenCalledWith("A tide app"),
    );
    expect(input.value).toBe("");
  });
});
