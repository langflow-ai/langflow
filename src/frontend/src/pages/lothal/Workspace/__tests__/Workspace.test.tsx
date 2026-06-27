import { fireEvent, render, screen, waitFor } from "@testing-library/react";

// jsdom has no scrollIntoView; the chat panel calls it on every message change.
Element.prototype.scrollIntoView = jest.fn();

const mockNavigate = jest.fn();
let mockParams: { projectId?: string } = { projectId: "p1" };
jest.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => mockParams,
}));

const mockUseProject = jest.fn();
const mockUseMessages = jest.fn();
const mockUseDiagram = jest.fn();
const mockUseCode = jest.fn();
const mockSendMutate = jest.fn();
const mockApproveMutate = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  useProject: () => mockUseProject(),
  useMessages: () => mockUseMessages(),
  useDiagram: () => mockUseDiagram(),
  useCode: () => mockUseCode(),
  useSendMessage: () => ({ mutateAsync: mockSendMutate, isPending: false }),
  useApproveDiagram: () => ({
    mutateAsync: mockApproveMutate,
    isPending: false,
  }),
}));

// Stub the live D2 canvas (real one needs SVG layout/pointer gestures). It fires
// onAnchor when clicked, so the integration test can drive the canvas → composer
// chip wiring (D.7) without the real pan/zoom surface.
jest.mock("../../components/D2Canvas", () => ({
  D2Canvas: ({ onAnchor }: { onAnchor?: (a: unknown) => void }) => (
    <button
      type="button"
      data-testid="d2-canvas"
      onClick={() =>
        onAnchor?.({ kind: "node", id: "checkout", label: "Checkout" })
      }
    />
  ),
}));

import Workspace from "../index";

const project = {
  id: "p1",
  user_id: "u1",
  name: "Tide Tracker",
  phase: "CLARIFICATION",
  prd_content: null,
  diagram_json: null,
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

const codeError501 = {
  response: {
    status: 501,
    data: {
      detail: "The code endpoint is not implemented yet.",
      status: "not_implemented",
    },
  },
};

const codeProject = { ...project, phase: "CODE_GENERATION" };

describe("Lothal Workspace", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockParams = { projectId: "p1" };
    mockSendMutate.mockResolvedValue(msg({ id: "reply", content: "ok" }));
    mockApproveMutate.mockResolvedValue({ phase: "CODE_GENERATION" });
    // Default: messages load fine and empty.
    mockUseMessages.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });
    // Default: the diagram query is idle (most tests use a CLARIFICATION
    // project, so the canvas shows its placeholder and never reads this).
    mockUseDiagram.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: undefined,
    });
    // Default: no code yet (the right pane only consults this in a code phase).
    mockUseCode.mockReturnValue({ data: [], isLoading: false, isError: false });
  });

  it("shows a themed loading state while projects load", () => {
    mockUseProject.mockReturnValue({ data: undefined, isLoading: true });
    render(<Workspace />);
    expect(screen.getByText("Opening your project…")).toBeInTheDocument();
  });

  it("shows a not-found state when no project matches the id", () => {
    mockUseProject.mockReturnValue({ data: undefined, isLoading: false });
    render(<Workspace />);
    expect(screen.getByText("Project not found")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to projects" }));
    expect(mockNavigate).toHaveBeenCalledWith("/lothal");
  });

  it("renders the shell — name, phase stepper, and status verb", () => {
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
    render(<Workspace />);
    expect(screen.getByText("Tide Tracker")).toBeInTheDocument();
    // PhaseStepper label + StatusDot verb for CLARIFICATION.
    expect(screen.getByText("Clarify")).toBeInTheDocument();
    expect(screen.getByText("clarifying")).toBeInTheDocument();
  });

  it("shows NotReady (not an error) when the messages endpoint 501s", () => {
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
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
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
    render(<Workspace />);
    expect(screen.getByText("Start the conversation")).toBeInTheDocument();
    // The input dock is always available.
    expect(screen.getByLabelText("Message")).toBeInTheDocument();
  });

  it("renders messages in order with a transition block at a phase boundary", () => {
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
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
          content: "Designing now",
          phase: "ARCHITECTURE",
        }),
      ],
    });
    render(<Workspace />);
    expect(screen.getByText("Build a tide app")).toBeInTheDocument();
    expect(screen.getByText("Who is it for?")).toBeInTheDocument();
    expect(
      screen.getByText("Requirements clear — designing the architecture"),
    ).toBeInTheDocument();
  });

  it("renders suggestion chips only on the latest clarification reply and sends on pick", () => {
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
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
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
    render(<Workspace />);
    // The composer is a contentEditable field (Epic D.7), so drive its DOM.
    const input = screen.getByLabelText("Message") as HTMLDivElement;
    input.appendChild(document.createTextNode("A tide app"));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(mockSendMutate).toHaveBeenCalledWith("A tide app"),
    );
    expect(input.textContent).toBe("");
  });

  it("drops a composer chip when a canvas element is anchored, and serializes it on send (D.7)", async () => {
    // Diagram phase so the right pane renders the (stubbed) D2 canvas.
    mockUseProject.mockReturnValue({
      data: { ...project, phase: "ARCHITECTURE" },
      isLoading: false,
    });
    mockUseDiagram.mockReturnValue({
      data: { d2: "user -> api", svg: "<svg>x</svg>" },
      isLoading: false,
      isError: false,
    });
    render(<Workspace />);

    // Double-clicking a canvas element resolves an anchor → the workspace routes
    // it to the composer, which drops an inline chip.
    fireEvent.click(screen.getByTestId("d2-canvas"));
    const editor = screen.getByLabelText("Message") as HTMLDivElement;
    const chip = editor.querySelector(".lothal-chip") as HTMLElement;
    expect(chip).toBeInTheDocument();
    expect(chip.dataset.id).toBe("checkout");
    expect(chip.textContent).toContain("Checkout");

    // On send the chip serializes to its exact anchor id, backtick-wrapped.
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() =>
      expect(mockSendMutate).toHaveBeenCalledWith("`checkout`"),
    );
  });

  // --- Approve diagram (Epic D.11) ---

  it("offers Approve only in ARCHITECTURE and approving calls the mutation", async () => {
    mockUseProject.mockReturnValue({
      data: { ...project, phase: "ARCHITECTURE" },
      isLoading: false,
    });
    mockUseDiagram.mockReturnValue({
      data: { d2: "user -> api", svg: "<svg>x</svg>" },
      isLoading: false,
      isError: false,
    });
    render(<Workspace />);

    const approve = screen.getByRole("button", {
      name: "Approve & generate code",
    });
    fireEvent.click(approve);
    await waitFor(() => expect(mockApproveMutate).toHaveBeenCalledTimes(1));
  });

  it("does not offer Approve before the architecture stage (CLARIFICATION)", () => {
    mockUseProject.mockReturnValue({
      data: { ...project, phase: "CLARIFICATION" },
      isLoading: false,
    });
    mockUseDiagram.mockReturnValue({
      data: { d2: null, svg: null },
      isLoading: false,
      isError: false,
    });
    render(<Workspace />);
    expect(
      screen.queryByRole("button", { name: "Approve & generate code" }),
    ).not.toBeInTheDocument();
  });

  // --- Code surface (right pane in code phases) ---

  it("shows the canvas (not code) while still in a diagram phase", () => {
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
    render(<Workspace />);
    expect(
      screen.getByText("The diagram takes shape here"),
    ).toBeInTheDocument();
  });

  it("renders the code surface with the file tree in a code phase", () => {
    mockUseProject.mockReturnValue({ data: codeProject, isLoading: false });
    mockUseCode.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { path: "src/main.py", content: 'print("alpha")\n' },
        { path: "README.md", content: "# Title\n" },
      ],
    });
    render(<Workspace />);
    // The tree shows the folder and the (non-active) sibling file.
    expect(screen.getByText("src")).toBeInTheDocument();
    expect(screen.getByText("README.md")).toBeInTheDocument();
    // The first file (src/main.py) is shown by default — its content renders.
    expect(screen.getByText('"alpha"')).toBeInTheDocument();
  });

  it("shows a file's content when selected in the code tree", () => {
    mockUseProject.mockReturnValue({ data: codeProject, isLoading: false });
    mockUseCode.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [
        { path: "src/main.py", content: 'print("alpha")\n' },
        { path: "README.md", content: "# Title\n" },
      ],
    });
    render(<Workspace />);
    fireEvent.click(screen.getByText("README.md"));
    expect(screen.getByText("# Title")).toBeInTheDocument();
  });

  it("shows NotReady (not an error) when the code endpoint 501s", () => {
    mockUseProject.mockReturnValue({ data: codeProject, isLoading: false });
    mockUseCode.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: codeError501,
    });
    render(<Workspace />);
    expect(screen.getByText("The code isn't ready yet")).toBeInTheDocument();
    expect(
      screen.getByText("The code endpoint is not implemented yet."),
    ).toBeInTheDocument();
  });

  it("shows a generic failure (not NotReady) when /code fails non-501", () => {
    mockUseProject.mockReturnValue({ data: codeProject, isLoading: false });
    mockUseCode.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("boom"),
    });
    render(<Workspace />);
    expect(screen.getByText("Couldn't load the code")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Something went wrong loading this. Try again in a moment.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the generating state while code files are still empty", () => {
    mockUseProject.mockReturnValue({ data: codeProject, isLoading: false });
    mockUseCode.mockReturnValue({ data: [], isLoading: false, isError: false });
    render(<Workspace />);
    expect(screen.getByText("Generating the code…")).toBeInTheDocument();
  });

  it("titles the tab 'project — Lothal' and restores the default on unmount", () => {
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
    const { unmount } = render(<Workspace />);
    expect(document.title).toBe("Tide Tracker — Lothal");
    unmount();
    expect(document.title).toBe("Lothal");
  });

  it("leaves the tab title alone while the project is still loading", () => {
    document.title = "Lothal";
    mockUseProject.mockReturnValue({ data: undefined, isLoading: true });
    render(<Workspace />);
    expect(document.title).toBe("Lothal");
  });

  // --- New: project-fetch error handling ---

  it("shows the not-found state when the project GET returns 404", () => {
    mockUseProject.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { response: { status: 404 } },
      refetch: jest.fn(),
    });
    render(<Workspace />);
    expect(screen.getByText("Project not found")).toBeInTheDocument();
    // Should NOT show the transient-error state.
    expect(
      screen.queryByText(/Couldn.t load this project/),
    ).not.toBeInTheDocument();
  });

  it("shows the error+retry state (not not-found) when the project GET 500s on all attempts", () => {
    const mockRefetch = jest.fn();
    mockUseProject.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { response: { status: 500 } },
      refetch: mockRefetch,
    });
    render(<Workspace />);
    expect(screen.getByText(/Couldn.t load this project/)).toBeInTheDocument();
    expect(
      screen.getByText(
        "Something went wrong reaching the server. Try again in a moment.",
      ),
    ).toBeInTheDocument();
    // Should NOT show the not-found state.
    expect(screen.queryByText("Project not found")).not.toBeInTheDocument();
    // Retry button calls refetch.
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mockRefetch).toHaveBeenCalled();
  });

  it("renders the version badge in the Workspace TopBar", () => {
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
    render(<Workspace />);
    // LOTHAL_VERSION may be "dev" or a semver string — the badge is always present.
    const badge = screen.getByText(/^v/);
    expect(badge).toBeInTheDocument();
  });

  it("navigates to /lothal/settings when the TopBar Settings affordance is clicked", () => {
    mockUseProject.mockReturnValue({ data: project, isLoading: false });
    render(<Workspace />);
    // The account/settings button uses aria-label containing "settings".
    const settingsBtn = screen.getByRole("button", { name: /settings/i });
    fireEvent.click(settingsBtn);
    expect(mockNavigate).toHaveBeenCalledWith("/lothal/settings");
  });
});
