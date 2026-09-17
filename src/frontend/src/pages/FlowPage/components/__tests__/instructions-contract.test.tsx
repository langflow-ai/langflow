import { act, render, screen } from "@testing-library/react";
import { InstructionsContract } from "../instructions-contract";

const post = jest.fn();
let state: { currentFlow: unknown; nodes: unknown[]; edges: unknown[] };
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: unknown[]) => post(...args) },
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (select: (state: unknown) => unknown) => select(state),
}));
jest.mock("react-router-dom", () => ({
  useSearchParams: () => [new URLSearchParams()],
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
  state = {
    currentFlow: {
      id: "flow",
      folder_id: "project",
      data: { harness_contract: { slot: "SystemPromptBuilder" } },
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
  const { rerender } = render(<InstructionsContract />);
  await tick();
  expect(screen.getByRole("status")).toHaveTextContent("Text output ready");
  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    "/all/folder/project?tab=harness&field=system_prompt",
  );
  post.mockResolvedValue({ data: { valid: false, outputs: [] } });
  state.nodes = [];
  rerender(<InstructionsContract />);
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
  const { rerender } = render(<InstructionsContract />);
  await tick();
  state.nodes = [];
  post.mockResolvedValue({ data: { valid: false, outputs: [] } });
  rerender(<InstructionsContract />);
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
  render(<InstructionsContract />);
  await tick();
  expect(post).not.toHaveBeenCalled();
  expect(screen.queryByTestId("instructions-contract")).not.toBeInTheDocument();
});
