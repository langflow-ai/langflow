import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { api } from "@/controllers/API/api";
import { migrationKeys } from "@/controllers/API/queries/migration";
import useAuthStore from "@/stores/authStore";
import type { Users } from "@/types/api";
import { axe } from "@/utils/a11y-test";
import UpgradeReportsPage from "..";
import { history, preview, report } from "./fixture";

function open(admin: boolean | null = true) {
  useAuthStore.setState({
    userData: admin === null ? null : ({ is_superuser: admin } as Users),
  });
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
      ? { maintenance: false, migration: false, running_jobs: 0 }
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

it("waits for the signed-in profile before deciding admin access", async () => {
  open(null);
  expect(screen.queryByText("Home")).not.toBeInTheDocument();
  expect(api.get).not.toHaveBeenCalled();
  act(() => {
    useAuthStore.setState({ userData: { is_superuser: true } as Users });
  });
  expect(
    await screen.findByRole("heading", { name: "Upgrade reports" }),
  ).toBeVisible();
  expect(screen.queryByText("Home")).not.toBeInTheDocument();
});

it("explains unverifiable provider selection and requires manual review", async () => {
  jest.spyOn(api, "post").mockResolvedValue({
    data: {
      ...preview,
      results: [
        {
          ...preview.results[0],
          status: "manual",
          reason_codes: ["provider_selection_unverifiable"],
        },
      ],
    },
  });
  open();
  await userEvent.click(
    await screen.findByRole("checkbox", {
      name: "Select Customer support for preview",
    }),
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Preview selected updates" }),
  );
  expect(
    await screen.findByText(
      "The selected model provider could not be verified. Review this flow manually.",
    ),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: /Apply .* reviewed update/ }),
  ).not.toBeInTheDocument();
});

it("redirects non-admins without reading reports", async () => {
  open(false);
  expect(await screen.findByText("Home")).toBeVisible();
  expect(api.get).not.toHaveBeenCalled();
});

it("explains the first action and keeps incomplete checks distinct from success", async () => {
  open();
  expect(
    screen.getByRole("heading", { name: "Start an upgrade review" }),
  ).toBeVisible();
  expect(
    screen.getByText(/Importing a report does not change any flows/),
  ).toBeVisible();
  expect(
    await screen.findByRole("heading", { name: "Assessment incomplete" }),
  ).toBeVisible();
  expect(
    screen.getByText(/correct the cause, and generate a new report/),
  ).toBeVisible();
  await userEvent.click(screen.getByText("What the results mean"));
  expect(
    screen.getByText(/This is an unknown result and requires review/),
  ).toBeVisible();
  expect(
    screen.queryByRole("heading", { name: "No compatibility problems found" }),
  ).not.toBeInTheDocument();
});

it.each([
  ["ok", "No compatibility problems found"],
  ["warn", "Review required before upgrading"],
  ["fail", "Compatibility problems found"],
])(
  "explains the next action for a complete %s assessment",
  async (status, title) => {
    const current = {
      ...report,
      document: {
        ...report.document,
        summary: { flows: { ok: 0, warn: 0, fail: 0, [status]: 1 }, nodes: {} },
      },
    };
    jest.spyOn(api, "get").mockImplementation(async (url) => ({
      data: url.endsWith(report.id)
        ? current
        : url.endsWith("/repairs")
          ? { items: [], total: 0 }
          : history,
    }));
    open();
    expect(await screen.findByRole("heading", { name: title })).toBeVisible();
    if (status === "ok")
      expect(
        screen.getByText(/This result does not certify an upgrade/),
      ).toBeVisible();
  },
);

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
  expect(
    screen.getByText(/Preview complete. No flows have changed/),
  ).toBeVisible();
  expect(
    screen.getByRole("list", { name: "Update results" }),
  ).toHaveTextContent("Customer support");
  expect(apply).toBeDisabled();
  await userEvent.click(
    screen.getByRole("checkbox", { name: /I reviewed this 1 update/ }),
  );
  expect(apply).toBeDisabled();
  act(() =>
    client.setQueryData(migrationKeys.pause, {
      maintenance: true,
      migration: false,
      running_jobs: 0,
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
    await screen.findByRole("link", {
      name: "Review protected recovery version for Customer support",
    }),
  ).toBeVisible();
  expect(
    screen.getByText(/Update request complete. Review each result/),
  ).toBeVisible();
});

async function reviewUpdate() {
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
  await userEvent.click(
    screen.getByRole("checkbox", { name: /I reviewed this 1 update/ }),
  );
  return apply;
}

it("keeps updates disabled until running jobs finish", async () => {
  const { client } = open();
  const apply = await reviewUpdate();

  act(() =>
    client.setQueryData(migrationKeys.pause, {
      maintenance: true,
      migration: false,
      running_jobs: 2,
    }),
  );
  expect(apply).toBeDisabled();
  expect(await screen.findByText(/2 jobs are still running/)).toBeVisible();

  act(() =>
    client.setQueryData(migrationKeys.pause, {
      maintenance: true,
      migration: false,
      running_jobs: 0,
    }),
  );
  await waitFor(() => expect(apply).toBeEnabled());
});

it.each([undefined, null, -1, Number.NaN, "0"])(
  "refuses updates when the running job count is %s",
  async (runningJobs) => {
    const { client } = open();
    const apply = await reviewUpdate();

    act(() =>
      client.setQueryData(migrationKeys.pause, {
        maintenance: true,
        migration: false,
        running_jobs: runningJobs,
      }),
    );

    expect(apply).toBeDisabled();
    expect(
      await screen.findByText(/Maintenance status could not be verified/),
    ).toBeVisible();
  },
);

it("explains a running-job refusal and refreshes maintenance status", async () => {
  let runningJobs = 0;
  jest.spyOn(api, "get").mockImplementation(async (url) => ({
    data: url.endsWith("/maintenance/status")
      ? { maintenance: true, migration: false, running_jobs: runningJobs }
      : url.endsWith("/repairs")
        ? { items: [], total: 0 }
        : url.endsWith(report.id)
          ? report
          : history,
  }));
  jest.spyOn(api, "post").mockImplementation(async (url) => {
    if (url.endsWith("/apply")) {
      runningJobs = 1;
      throw {
        isAxiosError: true,
        response: {
          status: 409,
          data: {
            detail: "Wait for running jobs to finish before applying repairs",
          },
        },
      };
    }
    return { data: preview };
  });
  open();
  const apply = await reviewUpdate();

  await userEvent.click(apply);

  expect(
    await screen.findByText(
      /The server refused the update because jobs were still running/,
    ),
  ).toBeVisible();
  expect(await screen.findByText(/1 job is still running/)).toBeVisible();
  expect(apply).toBeDisabled();
});

it.each([
  {
    isAxiosError: true,
    response: {
      status: 409,
      data: { detail: { private: "server diagnostics" } },
    },
  },
  { isAxiosError: true, request: {}, message: "server diagnostics" },
])(
  "uses a safe fallback for an unknown request failure %#",
  async (failure) => {
    jest.spyOn(api, "post").mockImplementation(async (url) => {
      if (url.endsWith("/apply")) {
        throw failure;
      }
      return { data: preview };
    });
    const { client } = open();
    const apply = await reviewUpdate();
    act(() =>
      client.setQueryData(migrationKeys.pause, {
        maintenance: true,
        migration: false,
        running_jobs: 0,
      }),
    );

    await userEvent.click(apply);

    expect(
      await screen.findByText(/The request could not finish/),
    ).toBeVisible();
    expect(screen.queryByText(/server diagnostics/)).not.toBeInTheDocument();
  },
);

it("explains maintenance against the live database and links its instructions", async () => {
  open();
  await screen.findByRole("heading", { name: "Customer support" });
  await userEvent.click(screen.getByText("How to enable maintenance"));

  expect(screen.getByText(/this installation’s live database/)).toBeVisible();
  expect(screen.getByText(/langflow maintenance on --reason/)).toBeVisible();
  expect(
    screen.getByRole("link", { name: "Maintenance instructions" }),
  ).toHaveAttribute("href", "https://docs.langflow.org/maintenance-mode");
});

it.each([
  [report.document.flows, "Customer support"],
  [
    [
      {
        ...report.document.flows[0],
        id: "saved-version",
        kind: "flow_version",
        flow_id: preview.results[0].flow_id,
      },
    ],
    "Customer support",
  ],
  [[], preview.results[0].flow_id],
])(
  "links saved outcomes using available flow metadata %#",
  async (flows, name) => {
    jest.spyOn(api, "get").mockImplementation(async (url) => ({
      data: url.endsWith("/maintenance/status")
        ? { maintenance: false, migration: false, running_jobs: 0 }
        : url.endsWith("/repairs")
          ? {
              total: 1,
              items: [
                {
                  id: "outcome-1",
                  created_at: report.created_at,
                  result: {
                    ...preview.results[0],
                    status: "updated",
                    recovery_version_id: "recovery-1",
                  },
                },
              ],
            }
          : url.endsWith(report.id)
            ? { ...report, document: { ...report.document, flows } }
            : history,
    }));
    open();
    await userEvent.click(await screen.findByText("Saved update outcomes"));

    expect(
      await screen.findByRole("link", { name: `Open ${name}` }),
    ).toHaveAttribute("href", `/flow/${preview.results[0].flow_id}`);
    expect(
      screen.getByRole("link", {
        name: `Review protected recovery version for ${name}`,
      }),
    ).toHaveAttribute(
      "href",
      `/flow/${preview.results[0].flow_id}?version=recovery-1`,
    );
  },
);

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
