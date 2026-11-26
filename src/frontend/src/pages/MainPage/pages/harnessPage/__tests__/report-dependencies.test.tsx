jest.mock("@/controllers/API/api", () => ({ api: { get: jest.fn() } }));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { api } from "@/controllers/API/api";
import type { ToolDependencyUse } from "@/controllers/API/queries/folders/use-project-tool-pack";
import { ReportDependencies } from "../components/report-dependencies";

const mockNavigate = jest.fn();
const mockOpen = jest.fn();
const recorded: ToolDependencyUse = {
  tool_call_id: "first-call",
  tool_name: "lookup_tool",
  binding: {
    reference: {
      project_id: "pack",
      expected_type: "tool-pack",
      revision: "a".repeat(64),
    },
    tool: {
      flow_id: "lookup",
      name: "Reviewed lookup",
      description: "Read sources",
      revision: "b".repeat(64),
    },
    version_id: "saved-snapshot",
  },
};
function mount(
  uses = [recorded, { ...recorded, tool_call_id: "second-call" }],
) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <ReportDependencies uses={uses} harnessId="harness" onOpen={mockOpen} />
    </QueryClientProvider>,
  );
}
beforeEach(() => jest.clearAllMocks());

it("groups completed calls and displays recorded revisions even when the current pack changes", async () => {
  jest.mocked(api.get).mockResolvedValue({
    data: {
      name: "Current research tools",
      reference: { ...recorded.binding.reference, revision: "c".repeat(64) },
      tools: [],
    },
  });
  mount();
  expect(
    await screen.findByText("Pack changed since this run"),
  ).toBeInTheDocument();
  expect(screen.getByText("2 completed calls")).toBeInTheDocument();
  expect(
    screen.getByText(recorded.binding.reference.revision),
  ).toBeInTheDocument();
  expect(screen.getByText(recorded.binding.tool.revision)).toBeInTheDocument();
  expect(screen.queryByText("c".repeat(64))).not.toBeInTheDocument();
  expect(screen.getByText("saved-snapshot")).toBeInTheDocument();
  expect(screen.getByText("lookup_tool · first-call")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Open Pack" }));
  expect(mockOpen).toHaveBeenCalled();
  expect(mockNavigate).toHaveBeenCalledWith(
    "/all/folder/pack?tab=harness&fromHarness=harness",
  );
});

it("retains historical evidence after access is lost and disables navigation to the unavailable project", async () => {
  jest.mocked(api.get).mockRejectedValue({ response: { status: 404 } });
  mount();
  expect(
    await screen.findByText(/The current pack is unavailable/),
  ).toBeInTheDocument();
  expect(screen.getByText("saved-snapshot")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open Pack" })).toBeDisabled();
});

it("does not invent dependency evidence for legacy reports", () => {
  mount([]);
  expect(screen.queryByRole("region")).not.toBeInTheDocument();
  expect(api.get).not.toHaveBeenCalled();
});
