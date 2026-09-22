import { act, render, screen } from "@testing-library/react";
import { HarnessFlowContract } from "../instructions-contract";

const post = jest.fn();
let searchParams = new URLSearchParams();
let state: { currentFlow: unknown; nodes: unknown[]; edges: unknown[] };
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: unknown[]) => post(...args) },
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (select: (state: unknown) => unknown) => select(state),
}));
jest.mock("react-router-dom", () => ({
  useSearchParams: () => [searchParams],
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
  ),
}));
const tick = () =>
  act(async () => {
    jest.advanceTimersByTime(450);
  });
beforeEach(() => {
  jest.useFakeTimers();
  post.mockReset();
  searchParams = new URLSearchParams();
  state = {
    currentFlow: {
      id: "flow",
      folder_id: "project",
      data: { harness_contract: { slot: "Instructions" } },
    },
    nodes: [{ id: "output", data: {} }],
    edges: [],
  };
});
afterEach(() => {
  jest.useRealTimers();
});

it("checks edits, reports an invalid output, and returns to the Instructions field", async () => {
  post.mockResolvedValue({ data: { valid: true, outputs: [{}] } });
  const { rerender } = render(<HarnessFlowContract />);
  await tick();
  expect(screen.getByRole("status")).toHaveTextContent("Text output ready");
  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    "/all/folder/project?tab=harness&field=system_prompt",
  );
  post.mockResolvedValue({ data: { valid: false, outputs: [] } });
  state.nodes = [];
  rerender(<HarnessFlowContract />);
  expect(screen.getByRole("status")).toHaveTextContent("Checking output");
  await tick();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Output needs attention",
  );
});

it("ignores a response for a previous graph", async () => {
  let resolveOld: (data: unknown) => void;
  post.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
  );
  const { rerender } = render(<HarnessFlowContract />);
  await tick();
  state.nodes = [];
  post.mockResolvedValue({ data: { valid: false, outputs: [] } });
  rerender(<HarnessFlowContract />);
  await tick();
  await act(async () => {
    resolveOld!({ data: { valid: true, outputs: [{}] } });
  });
  expect(screen.getByRole("status")).toHaveTextContent(
    "Output needs attention",
  );
});

it("does not label a plain flow as a harness contract", async () => {
  state.currentFlow = { id: "plain", folder_id: "project", data: {} };
  render(<HarnessFlowContract />);
  await tick();
  expect(post).not.toHaveBeenCalled();
  expect(screen.queryByTestId("instructions-contract")).not.toBeInTheDocument();
});

it("validates Hook flows against the Hook contract and returns to that field", async () => {
  state.currentFlow = {
    id: "hook",
    folder_id: "project",
    data: { harness_contract: { slot: "Hook" } },
  };
  post.mockResolvedValue({ data: { valid: true, outputs: [{}] } });
  render(<HarnessFlowContract />);
  await tick();
  expect(post).toHaveBeenLastCalledWith(
    expect.stringContaining("/project/flow-outputs/validate"),
    expect.any(Object),
    expect.objectContaining({ params: { field_name: "hooks" } }),
  );
  expect(screen.getByRole("status")).toHaveTextContent("Decision output ready");
  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    "/all/folder/project?tab=harness&field=hooks",
  );
});

it("uses explicit return context for an unmarked flow and discards previous-slot validation", async () => {
  let resolveOld: (data: unknown) => void;
  post.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
  );
  state.currentFlow = { id: "flow", folder_id: "project", data: {} };
  searchParams = new URLSearchParams("harnessField=system_prompt");
  const { rerender } = render(<HarnessFlowContract />);
  await tick();
  searchParams = new URLSearchParams("harnessField=hooks");
  post.mockResolvedValue({ data: { valid: false, outputs: [] } });
  rerender(<HarnessFlowContract />);
  await tick();
  await act(async () => {
    resolveOld!({ data: { valid: true, outputs: [{}] } });
  });
  expect(screen.getByRole("status")).toHaveTextContent(
    "Decision output needs attention",
  );
});
