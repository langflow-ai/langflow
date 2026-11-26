jest.mock("@/controllers/API/api", () => ({ api: { get: jest.fn() } }));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));
jest.mock("@/controllers/API/queries/folders/use-get-folders", () => ({
  useGetFoldersQuery: () => mockFolders,
}));

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { useState } from "react";
import { api } from "@/controllers/API/api";
import type {
  ToolPackManifest,
  ToolPackReference,
} from "@/controllers/API/queries/folders/use-project-tool-pack";
import type { FlowType } from "@/types/flow";
import { HarnessReturn, ToolPackPicker } from "../components/tool-pack-picker";
import { openSelect } from "./select-option";

const mockNavigate = jest.fn();
const mockOpen = jest.fn();
const mockChange = jest.fn();
const mockFolders = {
  data: [
    { id: "pack", name: "Research tools", project_type: "tool-pack" },
    { id: "plain", name: "Plain project", project_type: "flows" },
    { id: "agent", name: "Other harness", project_type: "agent-harness" },
  ],
  isLoading: false,
  isError: false,
  refetch: jest.fn(),
};
const reference: ToolPackReference = {
  project_id: "pack",
  expected_type: "tool-pack",
  revision: "a".repeat(64),
};
const oldTool = {
  flow_id: "lookup",
  name: "Source lookup",
  description: "Read sources",
  revision: "b".repeat(64),
};
const manifest: ToolPackManifest = {
  reference,
  name: "Research tools",
  tools: [oldTool],
};
const agent = {
  id: "agent",
  data: {
    nodes: [
      {
        id: "RunFlow-tool",
        data: {
          _harness_tool: {
            tool_pack: { reference, tool: oldTool, version_id: "snapshot" },
          },
        },
      },
    ],
    edges: [],
  },
} as unknown as FlowType;
const request = jest.mocked(api.get);

function mount(initial: ToolPackReference[] = [], enabled = true) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Form() {
    const [value, setValue] = useState(initial);
    return (
      <ToolPackPicker
        projectId="harness"
        agent={enabled ? agent : undefined}
        value={value}
        saved={initial}
        onOpen={mockOpen}
        onChange={(next) => {
          mockChange(next);
          setValue(next);
        }}
      />
    );
  }
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <Form />
      </QueryClientProvider>,
    ),
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  window.history.replaceState({}, "", "/");
  mockFolders.isError = false;
  request.mockResolvedValue({ data: manifest });
});

it("offers only tool packs, reviews exports, and changes the draft only on acceptance", async () => {
  mount();
  const chooser = screen.getByRole("combobox", { name: "Choose a Tool Pack" });
  const user = await openSelect(chooser);
  expect(
    screen.queryByRole("option", { name: "Plain project" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("option", { name: "Other harness" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("option", { name: "Research tools" }));
  fireEvent.click(screen.getByRole("button", { name: "Review Exports" }));
  const dialog = await screen.findByRole("dialog");
  expect(await within(dialog).findByText("Source lookup")).toBeInTheDocument();
  expect(mockChange).not.toHaveBeenCalled();
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Use This Revision" }),
  );
  expect(mockChange).toHaveBeenLastCalledWith([reference]);
  expect(
    await screen.findByText("Reviewed · save to apply"),
  ).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith(
    expect.stringContaining("/projects/pack/tool-pack"),
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  );
});

it("shows stale exports and replaces only the reviewed reference after explicit acceptance", async () => {
  request.mockResolvedValue({
    data: {
      ...manifest,
      reference: { ...reference, revision: "c".repeat(64) },
      tools: [
        {
          ...oldTool,
          description: "New lookup behavior",
          revision: "d".repeat(64),
        },
        {
          flow_id: "new-tool",
          name: "Cite sources",
          description: "Produce citations",
          revision: "e".repeat(64),
        },
      ],
    },
  });
  mount([reference]);
  expect(await screen.findByText("Changed since review")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Review Exports" }));
  const dialog = await screen.findByRole("dialog");
  expect(
    await within(dialog).findByText("Changed", { exact: true }),
  ).toBeInTheDocument();
  expect(
    within(dialog).getByText("Added", { exact: true }),
  ).toBeInTheDocument();
  expect(
    within(dialog).getByText("Source lookup: Read sources"),
  ).toBeInTheDocument();
  expect(mockChange).not.toHaveBeenCalled();
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Use This Revision" }),
  );
  expect(mockChange).toHaveBeenLastCalledWith([
    { ...reference, revision: "c".repeat(64) },
  ]);
});

it("keeps unavailable references removable and retries discovery without accepting anything", async () => {
  request.mockRejectedValue({ response: { status: 404 } });
  mount([reference]);
  expect(
    await screen.findByText(/This pack is unavailable/),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Review Exports" }));
  const dialog = await screen.findByRole("dialog");
  const retry = await within(dialog).findByRole("button", { name: "Retry" });
  request.mockResolvedValue({ data: manifest });
  fireEvent.click(retry);
  expect(await within(dialog).findByText("Source lookup")).toBeInTheDocument();
  expect(mockChange).not.toHaveBeenCalled();
  fireEvent.keyDown(dialog, { key: "Escape" });
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Remove Research tools" }),
  );
  expect(mockChange).toHaveBeenLastCalledWith([]);
});

it("preserves the draft callback when opening a dependency and offers a return route", async () => {
  mount([reference]);
  await screen.findByText("Matches the reviewed revision");
  fireEvent.click(screen.getByRole("button", { name: "Open Pack" }));
  expect(mockOpen).toHaveBeenCalledTimes(1);
  expect(mockNavigate).toHaveBeenCalledWith(
    "/all/folder/pack?tab=harness&fromHarness=harness",
  );
  window.history.replaceState(
    {},
    "",
    "/all/folder/pack?tab=harness&fromHarness=harness",
  );
  render(<HarnessReturn onOpen={mockOpen} />);
  fireEvent.click(screen.getByRole("button", { name: "Back To Harness" }));
  expect(mockNavigate).toHaveBeenLastCalledWith(
    "/all/folder/harness?tab=harness",
  );
});

it("requires an agent before adding", () => {
  mount([], false);
  expect(
    screen.getByRole("combobox", { name: "Choose a Tool Pack" }),
  ).toBeDisabled();
  expect(screen.getByRole("button", { name: "Review Exports" })).toBeDisabled();
});

it("can review removal of every exported tool without dropping the project reference", async () => {
  request.mockResolvedValue({
    data: {
      ...manifest,
      reference: { ...reference, revision: "c".repeat(64) },
      tools: [],
    },
  });
  mount([reference]);
  await screen.findByText("Changed since review");
  fireEvent.click(screen.getByRole("button", { name: "Review Exports" }));
  const dialog = await screen.findByRole("dialog");
  expect(
    await within(dialog).findByText("Removed", { exact: true }),
  ).toBeInTheDocument();
  const accept = within(dialog).getByRole("button", {
    name: "Use This Revision",
  });
  await waitFor(() => expect(accept).toBeEnabled());
  fireEvent.click(accept);
  expect(mockChange).toHaveBeenLastCalledWith([
    { ...reference, revision: "c".repeat(64) },
  ]);
});

it("keeps selected dependencies visible and removable when the project list fails", async () => {
  mockFolders.isError = true;
  mount([reference]);
  expect(
    screen.getByText("Could not load available projects."),
  ).toBeInTheDocument();
  await screen.findByText("Matches the reviewed revision");
  fireEvent.click(
    screen.getByRole("button", { name: "Remove Research tools" }),
  );
  expect(mockChange).toHaveBeenLastCalledWith([]);
});
