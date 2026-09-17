jest.unmock("react-markdown");
jest.mock("remark-gfm", () => () => {});
jest.mock("@/controllers/API/api", () => ({ api: { get: jest.fn() } }));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { api } from "@/controllers/API/api";
import type { SourcedReport } from "@/controllers/API/queries/folders/use-project-reports";
import { HarnessReports } from "../components/harness-reports";

const mockNavigate = jest.fn();
const request = jest.mocked(api.get);
const largeText = "Full original evidence, not the inspector preview.\n".repeat(
  3000,
);
const report: SourcedReport = {
  schema_version: 1,
  id: "report-one",
  title: "Research findings",
  created_at: "2026-09-15T12:00:00Z",
  execution: {
    flow_id: "flow-one",
    run_id: "run-one",
    node_id: "report-output",
  },
  markdown:
    "## Findings\n\nAlpha has three observations. [@alpha]\n\nBeta has two. [@beta]",
  sources: [
    {
      id: "alpha",
      title: "Alpha study",
      uri: "https://example.com/alpha",
      content: largeText,
      captured_at: "2026-09-15T11:59:00Z",
      availability: "available",
      unavailable_reason: "",
    },
    {
      id: "beta",
      title: "Beta study",
      uri: "fixture://beta",
      content: "Original beta evidence",
      captured_at: "2026-09-15T11:59:01Z",
      availability: "available",
      unavailable_reason: "",
    },
  ],
  source_uses: [
    {
      source_id: "alpha",
      tool_name: "read_source",
      tool_call_id: "call-alpha",
    },
  ],
  claim_support: "not_evaluated",
};
const summary = (value = report) => ({
  id: value.id,
  title: value.title,
  created_at: value.created_at,
  execution: value.execution,
  source_count: value.sources.length,
  citation_count: 2,
  unresolved_citation_count: 0,
  citations_resolved: true,
  claim_support: "not_evaluated",
});
const page = (items = [summary()], next_cursor: string | null = null) => ({
  items,
  next_cursor,
  unavailable_count: 0,
});

function mount(projectId = "project-one") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const view = render(
    <QueryClientProvider client={client}>
      <HarnessReports projectId={projectId} />
    </QueryClientProvider>,
  );
  return { ...view, client };
}
function open() {
  fireEvent.click(screen.getByRole("button", { name: "Reports" }));
}

beforeEach(() => {
  jest.clearAllMocks();
  request.mockImplementation(async (url) => ({
    data: String(url).endsWith("/reports") ? page() : report,
  }));
});

it("loads on demand and reads complete original evidence beside the report", async () => {
  const view = mount();
  expect(request).not.toHaveBeenCalled();
  open();
  await screen.findByRole("heading", { name: "Research findings" });
  expect(
    screen.getByTestId("report-source-content").textContent === largeText,
  ).toBe(true);
  expect(largeText.length).toBeGreaterThan(128000);
  expect(
    screen.getByText(
      "Whether the sources support the claims has not been evaluated.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Citations linked to captured sources: 2"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Inspect source 2" }));
  expect(screen.getByTestId("report-source-content")).toHaveTextContent(
    "Original beta evidence",
  );
  expect(screen.getByRole("combobox", { name: "Source evidence" })).toHaveValue(
    "beta",
  );
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "alpha" },
  });
  expect(
    screen.getByRole("link", { name: "https://example.com/alpha" }),
  ).toHaveAttribute("rel", "noopener noreferrer");
  fireEvent.click(screen.getByText("Collected by tool"));
  expect(screen.getByText("call-alpha")).toBeInTheDocument();
  fireEvent.click(screen.getByText("Execution details"));
  expect(screen.getByText("run-one")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Open Current Flow/i }));
  expect(mockNavigate).toHaveBeenCalledWith("/flow/flow-one");
  view.unmount();
  view.client.clear();
});

it("pages through reports and resets to the latest report on refresh", async () => {
  const older = { ...report, id: "older-report", title: "Earlier findings" };
  request.mockImplementation(async (url, config) => ({
    data: String(url).endsWith("/reports")
      ? (config?.params as { cursor?: string })?.cursor
        ? page([summary(older)])
        : page([summary()], "older-cursor")
      : String(url).endsWith("older-report")
        ? older
        : report,
  }));
  mount();
  open();
  await screen.findByRole("heading", { name: "Research findings" });
  fireEvent.click(screen.getByRole("button", { name: "Older" }));
  await screen.findByRole("heading", { name: "Earlier findings" });
  expect(
    request.mock.calls.some(
      ([url, config]) =>
        String(url).includes("project-one/reports") &&
        (config?.params as { cursor?: string })?.cursor === "older-cursor",
    ),
  ).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  await screen.findByRole("heading", { name: "Research findings" });
});

it("shows a useful empty state and does not request a nonexistent report", async () => {
  request.mockResolvedValue({ data: page([]) });
  mount();
  open();
  await screen.findByText("No saved reports yet");
  expect(request).toHaveBeenCalledTimes(1);
});

it("lets the user recover from a list failure", async () => {
  request.mockRejectedValueOnce(new Error("Offline"));
  mount();
  open();
  await screen.findByText("Could not load reports.");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByRole("heading", { name: "Research findings" });
});

it.each([
  [404, "This report is no longer available in this project."],
  [409, "This saved report is invalid. Its evidence could not be verified."],
  [500, "Could not open this report."],
])(
  "reports a %s detail failure without offering stale evidence downloads",
  async (status, message) => {
    request.mockImplementation(async (url) => {
      if (String(url).endsWith("/reports")) return { data: page() };
      throw { isAxiosError: true, response: { status } };
    });
    mount();
    open();
    await screen.findByText(message);
    expect(screen.queryByTestId("report-reader")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Download Markdown/i }),
    ).not.toBeInTheDocument();
  },
);

it("distinguishes missing and unavailable evidence and keeps unsafe URIs inert", async () => {
  const draft = {
    ...report,
    markdown: "Missing [@missing] and unavailable [@alpha]",
    sources: [
      {
        ...report.sources[0],
        uri: "javascript:alert(1)",
        availability: "unavailable",
        content: "",
        unavailable_reason: "Publisher denied access.",
      },
    ],
  };
  request.mockImplementation(async (url) => ({
    data: String(url).endsWith("/reports") ? page() : draft,
  }));
  mount();
  open();
  await screen.findByText("Unresolved citations: 2");
  expect(
    screen.getByText("This citation has no source record in the saved report."),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Inspect source 2" }));
  expect(screen.getByText("Publisher denied access.")).toBeInTheDocument();
  expect(
    within(screen.getByRole("complementary")).queryByRole("link"),
  ).not.toBeInTheDocument();
  expect(screen.queryByTestId("report-source-content")).not.toBeInTheDocument();
});

it("downloads the canonical record with auth and exposes recoverable download failures", async () => {
  const blob = new Blob([JSON.stringify(report)], { type: "application/json" });
  const createURL = jest.fn(() => "blob:report");
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: createURL,
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: jest.fn(),
  });
  const click = jest
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  mount();
  open();
  await screen.findByRole("heading", { name: "Research findings" });
  request.mockRejectedValueOnce(new Error("Download unavailable"));
  fireEvent.click(
    screen.getByRole("button", { name: /Download evidence JSON/i }),
  );
  await screen.findByText("Download failed. Try the download again.");
  expect(createURL).not.toHaveBeenCalled();
  request.mockResolvedValueOnce({ data: blob });
  fireEvent.click(
    screen.getByRole("button", { name: /Download evidence JSON/i }),
  );
  await waitFor(() => expect(createURL).toHaveBeenCalledWith(blob));
  expect(request).toHaveBeenLastCalledWith(
    expect.stringContaining(
      "/project-one/reports/flow-one/report-one/download/json",
    ),
    { responseType: "blob" },
  );
  expect(click).toHaveBeenCalledTimes(1);
  expect(
    screen.queryByText("Download failed. Try the download again."),
  ).not.toBeInTheDocument();
  click.mockRestore();
});
