import { TextEncoder } from "node:util";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { api } from "@/controllers/API/api";
import type { UpgradeCheckEvent } from "@/controllers/API/queries/upgrade-reports";
import RunCheck from "../RunCheck";

// Only the network is faked: a fetch whose body the test feeds event by event,
// so the real streaming request and parser run.
type Chunk = { value?: Uint8Array; done: boolean };
let signal: AbortSignal;
let requestBody: string;
let feed: (chunk: Chunk) => void;
const encode = (text: string) => new TextEncoder().encode(text);

function fakeStream(init: RequestInit, status = 200) {
  signal = init.signal as AbortSignal;
  requestBody = String(init.body);
  const queued: Chunk[] = [];
  let waiting: { ok: (chunk: Chunk) => void; fail: (e: Error) => void } | null =
    null;
  feed = (chunk) => {
    const reader = waiting;
    waiting = null;
    if (reader) reader.ok(chunk);
    else queued.push(chunk);
  };
  signal.addEventListener("abort", () =>
    waiting?.fail(new DOMException("aborted", "AbortError")),
  );
  return {
    ok: status < 400,
    status,
    body: {
      getReader: () => ({
        read: () =>
          queued.length
            ? Promise.resolve(queued.shift() as Chunk)
            : new Promise<Chunk>((ok, fail) => {
                waiting = { ok, fail };
              }),
      }),
    },
  };
}

function emit(...events: UpgradeCheckEvent[]) {
  for (const event of events)
    feed({ value: encode(`${JSON.stringify(event)}\n\n`), done: false });
}
const finish = () => feed({ done: true });
function refuse(body: object) {
  feed({ value: encode(JSON.stringify(body)), done: false });
  finish();
}

/** The leave guard needs a data router, so every render goes through one. */
function inRouter(element: ReactElement) {
  const router = createMemoryRouter(
    [
      { path: "/settings/upgrade-reports", element },
      { path: "/flows", element: <p>Flows</p> },
    ],
    { initialEntries: ["/settings/upgrade-reports"] },
  );
  return { router, element: <RouterProvider router={router} /> };
}

function open() {
  const onImported = jest.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const invalidate = jest.spyOn(client, "invalidateQueries");
  const view = render(
    inRouter(
      <QueryClientProvider client={client}>
        <RunCheck onSelectReport={onImported} />
      </QueryClientProvider>,
    ).element,
  );
  return { onImported, invalidate, view };
}

let status = 200;
async function start(version = "1.15.0") {
  await userEvent.type(screen.getByLabelText("Target version"), version);
  await userEvent.click(
    screen.getByRole("button", { name: "Check compatibility" }),
  );
  await waitFor(() => expect(fetch).toHaveBeenCalled());
}

beforeEach(() => {
  status = 200;
  jest.spyOn(api, "get").mockResolvedValue({
    data: { current: "1.14.0", package: "langflow", releases: ["1.15.0"] },
  });
  jest
    .spyOn(global, "fetch")
    .mockImplementation(
      async (_url, init) => fakeStream(init!, status) as never,
    );
});
afterEach(() => jest.restoreAllMocks());

it("starts idle with the check button off until a release is typed", async () => {
  open();
  const button = screen.getByRole("button", { name: "Check compatibility" });
  expect(button).toBeDisabled();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Target version"), "1.15.0");
  expect(button).toBeEnabled();
});

it("offers fetched releases and the installed one when the field gets focus", async () => {
  open();
  const field = screen.getByRole("combobox", { name: "Target version" });
  expect(field).toHaveAttribute("placeholder", "Select or enter a version");
  await userEvent.click(field);
  const list = await screen.findByRole("listbox", { name: "Target version" });
  const options = within(list).getAllByRole("option");
  expect(options).toHaveLength(2);
  expect(options[0]).toHaveAccessibleName("Langflow 1.15.0");
  expect(options[1]).toHaveAccessibleName(/^Langflow 1\.14\.0/);
  expect(within(options[1]).getByText("Installed")).toBeVisible();
  await userEvent.click(options[0]);
  expect(field).toHaveValue("1.15.0");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("chooses a suggested release with the keyboard without submitting", async () => {
  open();
  const field = screen.getByRole("combobox", { name: "Target version" });
  // A typed value makes Enter able to submit, so choosing must stop it.
  await userEvent.type(field, "1.1");
  await screen.findByRole("listbox");
  await userEvent.keyboard("{ArrowUp}{Enter}");
  expect(field).toHaveValue("1.14.0");
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.keyboard("{ArrowDown}");
  expect(screen.getByRole("listbox")).toBeVisible();
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
});

it("still lets the admin type a release when the releases query fails", async () => {
  jest.spyOn(api, "get").mockRejectedValue(new Error("502"));
  open();
  await start("1.16.0");
  expect(JSON.parse(requestBody)).toEqual({ target_version: "1.16.0" });
});

it("says what is happening, then counts checked flows", async () => {
  open();
  await start();
  expect(JSON.parse(requestBody)).toEqual({ target_version: "1.15.0" });
  emit({ event: "started", target_version: "1.15.0", download: true });
  expect(
    await screen.findByText(/Downloading Langflow 1.15.0 and checking flows/),
  ).toBeInTheDocument();
  emit({ event: "flow", status: "ok" }, { event: "flow", status: "warn" });
  expect(await screen.findByText(/Checked 2 flows\./)).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Checked 2 flows.");
  expect(
    screen.getByRole("button", { name: "Check compatibility" }),
  ).toBeDisabled();
});

it("moves the progress bar toward the total once flows are checked", async () => {
  open();
  await start();
  emit({
    event: "started",
    target_version: "1.15.0",
    download: true,
    total: 4,
  });
  const bar = await screen.findByRole("progressbar", {
    name: "Upgrade check progress",
  });
  // Downloading gives no count, so the bar has no value yet.
  expect(bar).not.toHaveAttribute("aria-valuenow");
  emit({ event: "flow", status: "ok" });
  expect(await screen.findByText("Checked 1 of 4 flows.")).toBeInTheDocument();
  expect(bar).toHaveAttribute("aria-valuenow", "1");
  expect(bar).toHaveAttribute("aria-valuemax", "4");
});

it("stops counting toward the total when saved versions go past it", async () => {
  open();
  await start();
  emit(
    { event: "started", target_version: "1.15.0", download: true, total: 1 },
    { event: "flow", status: "ok" },
    { event: "flow", status: "ok" },
  );
  expect(await screen.findByText("Checked 2 flows.")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).not.toHaveAttribute("aria-valuenow");
});

it("does not say it downloads when the target is the running release", async () => {
  open();
  await start("1.14.0");
  emit({ event: "started", target_version: "1.14.0", download: false });
  expect(
    await screen.findByText(/Checking flows with Langflow 1.14.0/),
  ).toBeInTheDocument();
  expect(screen.queryByText(/Downloading/)).not.toBeInTheDocument();
});

it("cancel aborts the request and says the check was cancelled", async () => {
  open();
  await start();
  emit({ event: "started", target_version: "1.15.0", download: true });
  await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
  expect(signal.aborted).toBe(true);
  finish();
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Compatibility check canceled.",
  );
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Target version"), "1");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Check compatibility" }),
  ).toBeEnabled();
});

it.each(["target", "button"])(
  "moves keyboard focus through the check started from the %s",
  async (from) => {
    const user = userEvent.setup();
    open();
    await user.type(screen.getByLabelText("Target version"), "1.15.0");
    if (from === "button") await user.tab();

    await user.keyboard("{Enter}");
    const cancel = await screen.findByRole("button", { name: "Cancel" });
    expect(cancel).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(
      screen.getByRole("button", { name: "Check compatibility" }),
    ).toHaveFocus();
    expect(signal.aborted).toBe(true);
  },
);

it("returns focus after a failed check when Cancel had focus", async () => {
  open();
  await start();
  expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  emit({ event: "error", code: "check_running" });
  finish();
  await screen.findByRole("alert");
  expect(
    screen.getByRole("button", { name: "Check compatibility" }),
  ).toHaveFocus();
});

it("aborts the request when the page is left", async () => {
  const view = render(
    inRouter(
      <QueryClientProvider client={new QueryClient()}>
        <RunCheck onSelectReport={jest.fn()} />
      </QueryClientProvider>,
    ).element,
  );
  await userEvent.type(screen.getByLabelText("Target version"), "1.15.0");
  await userEvent.click(
    screen.getByRole("button", { name: "Check compatibility" }),
  );
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  view.unmount();
  expect(signal.aborted).toBe(true);
});

it("says the report is ready, what it found and what comes next", async () => {
  const { onImported, invalidate } = open();
  await start();
  emit(
    { event: "started", target_version: "1.15.0", download: true, total: 3 },
    { event: "flow", status: "ok" },
    {
      event: "imported",
      report_id: "r-1",
      flows: { ok: 1, warn: 1, fail: 1 },
    },
  );
  finish();
  await waitFor(() => expect(onImported).toHaveBeenCalledWith("r-1"));
  expect(invalidate).toHaveBeenCalledWith({
    queryKey: ["useGetUpgradeReports"],
  });
  const status = screen.getByRole("status");
  expect(status).toHaveTextContent("The report for Langflow 1.15.0 is ready.");
  expect(status).toHaveTextContent(
    "Ready: 1 · Review required: 1 · Needs repair: 1",
  );
  expect(status).toHaveTextContent(
    "upgrade it to Langflow 1.15.0, and update those flows from the same report.",
  );
  expect(
    screen.getByRole("button", { name: "Check compatibility" }),
  ).toBeEnabled();
});

it("says no flow needs changes when the running release finds nothing", async () => {
  open();
  await start("1.14.0");
  emit(
    { event: "started", target_version: "1.14.0", download: false, total: 1 },
    { event: "flow", status: "ok" },
    {
      event: "imported",
      report_id: "r-2",
      incomplete: false,
      flows: { ok: 1, warn: 0, fail: 0 },
    },
  );
  finish();
  expect(await screen.findByText("No flow needs changes.")).toBeInTheDocument();
});

it("view report selects the completed check's report and requests focus", async () => {
  const { onImported } = open();
  await start();
  emit({ event: "imported", report_id: "r-1" });
  finish();
  await userEvent.click(
    await screen.findByRole("button", { name: "View report" }),
  );
  expect(onImported).toHaveBeenLastCalledWith("r-1", true);
});

it.each([true, undefined])(
  "does not recommend an upgrade when completeness is %s",
  async (incomplete) => {
    open();
    await start();
    emit({
      event: "imported",
      report_id: "r-3",
      incomplete,
      flows: { ok: 2, warn: 0, fail: 0 },
    });
    finish();
    await screen.findByRole("button", { name: "View report" });
    const status = screen.getByRole("status");
    expect(status).not.toHaveTextContent(
      /you can upgrade|no flow needs changes/i,
    );
    if (incomplete) expect(status).toHaveTextContent("Assessment incomplete");
  },
);

it("clears the finished message when the admin types another release", async () => {
  open();
  await start();
  emit({ event: "imported", report_id: "r-1" });
  finish();
  await screen.findByRole("button", { name: "View report" });
  await userEvent.type(screen.getByLabelText("Target version"), "1");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it.each([
  ["check_running", /already running on this server/],
  ["uvx_unavailable", /uvx is not installed/],
  ["invalid_target_version", /1\.14\.0 or newer/],
  ["install_failed", /could not be installed or started/],
  ["timeout", /ran for 60 minutes/],
  ["import_refused", /imports are paused/],
  ["invalid_upgrade_report", /report was rejected/],
  [
    "unsupported_upgrade_report_format",
    /report format this server cannot import/,
  ],
  ["subprocess_unavailable", /cannot start the check from this page/],
  ["check_failed", /could not finish/],
])("shows the %s error from the stream", async (code, text) => {
  open();
  await start();
  emit({ event: "error", code, message: "server said" });
  finish();
  expect(await screen.findByRole("alert")).toHaveTextContent(text);
  expect(
    screen.getByRole("button", { name: "Check compatibility" }),
  ).toBeEnabled();
});

it("adds the server message under check_failed and install_failed", async () => {
  open();
  await start();
  emit({ event: "error", code: "check_failed", message: "boom in node 3" });
  finish();
  expect(await screen.findByText("boom in node 3")).toBeInTheDocument();
});

it.each([
  [409, { detail: { code: "check_running" } }, /already running/],
  [503, { detail: { code: "uvx_unavailable" } }, /uvx is not installed/],
  [422, { detail: { code: "invalid_target_version" } }, /1\.14\.0 or newer/],
])("shows the %s refusal before streaming", async (code, body, text) => {
  status = code;
  open();
  await start();
  refuse(body);
  expect(await screen.findByRole("alert")).toHaveTextContent(text);
});

it.each([
  ["invalid_target_version", "true"],
  ["import_refused", "false"],
  ["install_failed", "false"],
])("sets aria-invalid appropriately for %s", async (code, invalid) => {
  open();
  await start();
  emit({ event: "error", code, message: "server said" });
  finish();
  await screen.findByRole("alert");
  expect(screen.getByLabelText("Target version")).toHaveAttribute(
    "aria-invalid",
    invalid,
  );
});

it("shows the install failure detail without assuming a PyPI connection problem", async () => {
  open();
  await start();
  emit({
    event: "error",
    code: "install_failed",
    message: "No version of langflow matches the requested release",
  });
  finish();
  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("No version of langflow matches");
  expect(alert).not.toHaveTextContent("PyPI");
});

it("shows the server text of a refusal that has no code", async () => {
  status = 503;
  open();
  await start();
  // What the pause answers with: a string, not an object.
  refuse({ detail: "This instance is being migrated." });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This instance is being migrated.",
  );
});

it("says the server did not start the check when a refusal has no text", async () => {
  status = 502;
  open();
  await start();
  finish();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The server did not start the check.",
  );
});

it("reports a lost connection when the stream ends without a result", async () => {
  open();
  await start();
  emit({ event: "flow", status: "ok" });
  finish();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    /connection closed/,
  );
});

it("clears the error when the admin edits the release", async () => {
  open();
  await start();
  emit({ event: "error", code: "timeout" });
  finish();
  await screen.findByRole("alert");
  await userEvent.type(screen.getByLabelText("Target version"), "1");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

function openWithLink() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const { router, element } = inRouter(
    <QueryClientProvider client={client}>
      <RunCheck onSelectReport={jest.fn()} />
    </QueryClientProvider>,
  );
  render(element);
  return router;
}

it("asks before leaving a running check, and stays when told to", async () => {
  const router = openWithLink();
  await start();
  emit({ event: "started", target_version: "1.15.0", download: true });
  await act(() => router.navigate("/flows"));
  const dialog = await screen.findByRole("dialog", {
    name: "Leave the compatibility check?",
  });
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Stay on page" }),
  );
  expect(router.state.location.pathname).toBe("/settings/upgrade-reports");
  expect(signal.aborted).toBe(false);
  expect(screen.getByRole("progressbar")).toBeInTheDocument();
});

it("cancels the check when the admin chooses to leave", async () => {
  const router = openWithLink();
  await start();
  emit({ event: "started", target_version: "1.15.0", download: true });
  await act(() => router.navigate("/flows"));
  await userEvent.click(
    await screen.findByRole("button", { name: "Cancel check and leave" }),
  );
  expect(signal.aborted).toBe(true);
  expect(await screen.findByText("Flows")).toBeInTheDocument();
});

it("leaves without asking when no check is running", async () => {
  const router = openWithLink();
  await act(() => router.navigate("/flows"));
  expect(await screen.findByText("Flows")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("warns the browser before unloading while a check runs", async () => {
  openWithLink();
  await start();
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  expect(event.defaultPrevented).toBe(true);
});

it("stays on the page when the check ends while the leave dialog is open", async () => {
  const router = openWithLink();
  await start();
  emit({ event: "started", target_version: "1.15.0", download: true });
  await act(() => router.navigate("/flows"));
  expect(
    await screen.findByRole("dialog", {
      name: "Leave the compatibility check?",
    }),
  ).toBeVisible();
  emit({ event: "error", code: "check_failed", message: "boom" });
  finish();
  expect(await screen.findByRole("alert")).toBeVisible();
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(router.state.location.pathname).toBe("/settings/upgrade-reports");
});
