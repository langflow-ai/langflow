import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Project, PrototypeState } from "@/controllers/API/queries/lothal";

// The pane reads GET /prototype, auto-seeds generation, embeds OD's own project
// page, and approves. Mock the query layer; NotReady (the 501/error surface) is
// the real component.
const mockUsePrototype = jest.fn();
const mockUseGeneratePrototype = jest.fn();
const mockGenerateMutate = jest.fn();
const mockApproveMutate = jest.fn();
jest.mock("@/controllers/API/queries/lothal", () => ({
  usePrototype: (...args: unknown[]) => mockUsePrototype(...args),
  useGeneratePrototype: () => mockUseGeneratePrototype(),
  useApprovePrototype: () => ({
    mutateAsync: mockApproveMutate,
    isPending: false,
  }),
}));

import { PrototypePane } from "../PrototypePane";

const project = (over: Partial<Project> = {}): Project =>
  ({
    id: "p1",
    user_id: "u1",
    name: "Tide Tracker",
    phase: "PROTOTYPE",
    prd_content: null,
    diagram_json: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...over,
  }) as Project;

const state = (over: Partial<PrototypeState> = {}): PrototypeState => ({
  status: "READY",
  od_project_id: "od-1",
  od_conversation_id: "conv-1",
  embed_url: null,
  preview_html: null,
  artifacts: [],
  ...over,
});

const EMBED = "http://od.test/projects/od-1";

const ok = (data: PrototypeState) => ({
  data,
  isLoading: false,
  isError: false,
  error: undefined,
});

beforeEach(() => {
  jest.clearAllMocks();
  mockApproveMutate.mockResolvedValue({ phase: "CODE_GENERATION" });
  mockUseGeneratePrototype.mockReturnValue({
    mutate: mockGenerateMutate,
    isPending: false,
    isError: false,
  });
});

describe("PrototypePane", () => {
  it("auto-triggers generation when the state is IDLE", async () => {
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "IDLE", od_project_id: null })),
    );
    render(<PrototypePane project={project()} />);
    await waitFor(() => expect(mockGenerateMutate).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/Starting your prototype/i)).toBeInTheDocument();
  });

  it("does not generate while already GENERATING, and shows the building state", () => {
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "GENERATING", artifacts: [] })),
    );
    render(<PrototypePane project={project()} />);
    expect(mockGenerateMutate).not.toHaveBeenCalled();
    expect(screen.getByText(/Building your prototype/i)).toBeInTheDocument();
  });

  it("embeds OD's own project page when an embed URL is available", () => {
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "READY", embed_url: EMBED })),
    );
    render(<PrototypePane project={project()} />);
    const frame = screen.getByTitle(
      "Open Design prototype",
    ) as HTMLIFrameElement;
    expect(frame).toBeInTheDocument();
    expect(frame.getAttribute("src")).toBe(EMBED);
  });

  it("shows the finished prototype read-only (preview, no OD chrome/approve) when past PROTOTYPE", () => {
    mockUsePrototype.mockReturnValue(
      ok(
        state({
          status: "APPROVED",
          embed_url: EMBED,
          preview_html: "<html><body>Built screen</body></html>",
        }),
      ),
    );
    render(<PrototypePane project={project({ phase: "PLAN" })} />);
    // The finished design renders in the sandboxed preview frame…
    const preview = screen.getByTitle("Prototype preview") as HTMLIFrameElement;
    expect(preview).toBeInTheDocument();
    expect(preview).toHaveAttribute("sandbox");
    // …and OD's live editor + the approve action are NOT shown (read-only).
    expect(
      screen.queryByTitle("Open Design prototype"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Approve/ }),
    ).not.toBeInTheDocument();
  });

  it("shows a 'no prototype' note when revisiting an approved stage with nothing captured", () => {
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "APPROVED", embed_url: EMBED, preview_html: null })),
    );
    render(<PrototypePane project={project({ phase: "PLAN" })} />);
    expect(screen.getByText("No prototype to show")).toBeInTheDocument();
    expect(
      screen.queryByTitle("Open Design prototype"),
    ).not.toBeInTheDocument();
  });

  it("keeps embedding OD while a refine re-run is GENERATING (no flicker to placeholder)", () => {
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "GENERATING", embed_url: EMBED })),
    );
    render(<PrototypePane project={project()} />);
    // OD's own UI shows refine progress; we keep its frame mounted.
    expect(screen.getByTitle("Open Design prototype")).toBeInTheDocument();
    expect(screen.queryByText(/Building your prototype/i)).toBeNull();
  });

  it("lists artifacts when OD can't be embedded (no public base configured)", () => {
    mockUsePrototype.mockReturnValue(
      ok(
        state({
          status: "READY",
          embed_url: null,
          artifacts: [
            {
              path: "deck.pptx",
              kind: "deck",
              title: "Slides",
              preview_url: "https://od/x",
            },
          ],
        }),
      ),
    );
    render(<PrototypePane project={project()} />);
    expect(screen.getByText("Slides")).toBeInTheDocument();
    expect(screen.getByText("Open preview ↗")).toHaveAttribute(
      "href",
      "https://od/x",
    );
  });

  it("approves the prototype via the approve action", async () => {
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "READY", embed_url: EMBED })),
    );
    render(<PrototypePane project={project()} />);
    fireEvent.click(screen.getByText("Approve & generate code"));
    await waitFor(() => expect(mockApproveMutate).toHaveBeenCalledTimes(1));
  });

  it("offers an 'Open in new tab' convenience link to the embed URL", () => {
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "READY", embed_url: EMBED })),
    );
    render(<PrototypePane project={project()} />);
    expect(screen.getByText("Open in new tab ↗")).toHaveAttribute(
      "href",
      EMBED,
    );
  });

  it("shows the NotReady state on a structured 501", () => {
    mockUsePrototype.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: {
        response: {
          status: 501,
          data: { detail: "not yet", status: "not_implemented" },
        },
      },
    });
    render(<PrototypePane project={project()} />);
    expect(screen.getByText(/isn't live yet/i)).toBeInTheDocument();
  });

  it("shows a loading line while opening", () => {
    mockUsePrototype.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: undefined,
    });
    render(<PrototypePane project={project()} />);
    expect(screen.getByText(/Opening the prototype/i)).toBeInTheDocument();
  });

  it("shows a generic load error (not NotImplemented) on a non-501 failure", () => {
    mockUsePrototype.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: { response: { status: 502 } },
    });
    render(<PrototypePane project={project()} />);
    expect(screen.getByText("Couldn't load the prototype")).toBeInTheDocument();
  });

  it("surfaces a retry when the auto-generate kick fails (no dead-end)", async () => {
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "IDLE", od_project_id: null })),
    );
    mockUseGeneratePrototype.mockReturnValue({
      mutate: mockGenerateMutate,
      isPending: false,
      isError: true,
    });
    render(<PrototypePane project={project()} />);
    expect(
      screen.getByText("Couldn't start the prototype"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    // The auto-seed effect fired once on mount; Retry fires it again.
    await waitFor(() =>
      expect(mockGenerateMutate.mock.calls.length).toBeGreaterThanOrEqual(2),
    );
  });

  it("surfaces an approve failure inline and lets the user retry", async () => {
    mockApproveMutate.mockRejectedValueOnce(new Error("boom"));
    mockUsePrototype.mockReturnValue(
      ok(state({ status: "READY", embed_url: EMBED })),
    );
    render(<PrototypePane project={project()} />);
    fireEvent.click(screen.getByText("Approve & generate code"));
    await waitFor(() =>
      expect(
        screen.getByText(/Couldn.t approve just now/i),
      ).toBeInTheDocument(),
    );
  });
});
