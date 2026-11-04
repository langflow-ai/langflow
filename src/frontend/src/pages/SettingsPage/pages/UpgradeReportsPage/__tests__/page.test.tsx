import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { api } from "@/controllers/API/api";
import useAuthStore from "@/stores/authStore";
import type { Users } from "@/types/api";
import { axe } from "@/utils/a11y-test";
import UpgradeReportsPage from "..";
import { history, preview, report } from "./fixture";

function open(admin = true) {
  useAuthStore.setState({ userData: { is_superuser: admin } as Users });
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  const view = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/settings/upgrade-reports"]}>
        <Routes>
          <Route
            path="/settings/upgrade-reports"
            element={
              <main>
                <h1>Settings</h1>
                <UpgradeReportsPage />
              </main>
            }
          />
          <Route path="/" element={<p>Home</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...view, client };
}

beforeEach(() => {
  jest.spyOn(api, "get").mockImplementation(async (url) => ({
    data: url.endsWith("/maintenance/status")
      ? { maintenance: false, migration: false }
      : url.endsWith("/repairs")
        ? { items: [], total: 0 }
        : url.endsWith(report.id)
          ? report
          : history,
  }));
  jest.spyOn(api, "post").mockImplementation(async (url) => ({
    data: url.endsWith("/preview")
      ? preview
      : url.endsWith("/apply")
        ? {
            ...preview,
            results: [
              {
                ...preview.results[0],
                status: "updated",
                recovery_version_id: "recovery-1",
              },
            ],
          }
        : report,
  }));
});
afterEach(() => jest.restoreAllMocks());

it("redirects non-admins without reading reports", async () => {
  open(false);
  expect(await screen.findByText("Home")).toBeVisible();
  expect(api.get).not.toHaveBeenCalled();
});

it("shows unknown metadata, incomplete older reports, and retained-history limits", async () => {
  open();
  expect(
    await screen.findByRole("heading", { name: "Customer support" }),
  ).toBeVisible();
  expect(screen.getByText(/This older report lists 1 of 3/)).toBeVisible();
  await userEvent.click(screen.getByText("Usage, deployments, and findings"));
  expect(
    screen.getByText(/does not prove that the flow never ran/),
  ).toBeVisible();
  expect(screen.getByText(/Execution history is unavailable/)).toBeVisible();
  expect(screen.getByText("Tool discovery was unavailable.")).toBeVisible();
  await userEvent.selectOptions(
    screen.getByLabelText("Filter by result"),
    "fail",
  );
  expect(
    screen.queryByRole("heading", { name: "Customer support" }),
  ).not.toBeInTheDocument();
  await userEvent.selectOptions(
    screen.getByLabelText("Filter by result"),
    "could_not_verify",
  );
  expect(
    screen.getByRole("heading", { name: "Customer support" }),
  ).toBeVisible();
  await userEvent.type(
    screen.getByLabelText("Search names, owners, projects, or labels"),
    "grace",
  );
  expect(
    screen.getByRole("heading", { name: "Customer support" }),
  ).toBeVisible();
});

it("requires preview, maintenance, and explicit confirmation before applying server tokens", async () => {
  const { client } = open();
  await userEvent.click(
    await screen.findByRole("checkbox", {
      name: "Select Customer support for preview",
    }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Preview selected updates" }),
  );
  const apply = await screen.findByRole("button", {
    name: "Apply 1 reviewed update",
  });
  expect(apply).toBeDisabled();
  await userEvent.click(
    screen.getByRole("checkbox", { name: /I reviewed this 1 update/ }),
  );
  expect(apply).toBeDisabled();
  act(() =>
    client.setQueryData(["useUpgradeMaintenance"], {
      maintenance: true,
      migration: false,
    }),
  );
  await userEvent.click(apply);
  await waitFor(() =>
    expect(api.post).toHaveBeenCalledWith(
      expect.stringContaining("/upgrade-repairs/apply"),
      {
        flows: [
          {
            flow_id: report.document.flows[0].id,
            version_token: null,
            data_sha256: "c".repeat(64),
          },
        ],
        target_sha256: "b".repeat(64),
        report_id: report.id,
      },
    ),
  );
  expect(
    await screen.findByText("Protected recovery version recovery-1"),
  ).toBeVisible();
});

it("clears reviewed updates when the selected flows change", async () => {
  open();
  const checkbox = await screen.findByRole("checkbox", {
    name: "Select Customer support for preview",
  });
  await userEvent.click(checkbox);
  await userEvent.click(
    screen.getByRole("button", { name: "Preview selected updates" }),
  );
  await screen.findByRole("button", { name: "Apply 1 reviewed update" });
  await userEvent.click(checkbox);
  expect(
    screen.queryByRole("button", { name: "Apply 1 reviewed update" }),
  ).not.toBeInTheDocument();
});

it("has no axe violations in populated and selected preview states", async () => {
  const { container } = open();
  await screen.findByRole("heading", { name: "Customer support" });
  expect(await axe(container)).toHaveNoViolations();
  await userEvent.click(
    screen.getByRole("checkbox", {
      name: "Select Customer support for preview",
    }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Preview selected updates" }),
  );
  await screen.findByRole("button", { name: "Apply 1 reviewed update" });
  expect(await axe(container)).toHaveNoViolations();
});

it("ignores a preview that finishes after selection changes", async () => {
  let finish: (value: { data: typeof preview }) => void = () => {};
  const pending = new Promise<{ data: typeof preview }>((resolve) => {
    finish = resolve;
  });
  jest.spyOn(api, "post").mockImplementation(() => pending);
  open();
  const selection = await screen.findByRole("checkbox", {
    name: "Select Customer support for preview",
  });
  await userEvent.click(selection);
  await userEvent.click(
    screen.getByRole("button", { name: "Preview selected updates" }),
  );
  await userEvent.click(selection);
  await act(async () => {
    finish({ data: preview });
    await pending;
  });
  expect(
    screen.queryByRole("button", { name: "Apply 1 reviewed update" }),
  ).not.toBeInTheDocument();
});

it("explains an unsupported imported format", async () => {
  jest.spyOn(api, "post").mockRejectedValue({
    isAxiosError: true,
    response: {
      status: 422,
      data: { detail: { code: "unsupported_upgrade_report_format" } },
    },
  });
  open();
  const file = new File(['{"format_version":2}'], "report.json", {
    type: "application/json",
  });
  Object.defineProperty(file, "text", {
    value: async () => '{"format_version":2}',
  });
  await userEvent.upload(screen.getByLabelText("Checker report file"), file);
  await userEvent.click(screen.getByRole("button", { name: "Import report" }));
  expect(
    await screen.findByText(
      /This report format is not supported by this server/,
    ),
  ).toBeVisible();
});
