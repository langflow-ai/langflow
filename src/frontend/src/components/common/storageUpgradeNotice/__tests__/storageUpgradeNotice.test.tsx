import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import type { StorageUpgradeStatus } from "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status";
import { useGetStorageStatus } from "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status";
import { usePostStorageRetry } from "@/controllers/API/queries/knowledge-base-storage/use-post-storage-retry";
import { axe } from "@/utils/a11y-test";
import { StorageUpgradeNotice, StorageUpgradePanel } from "..";

jest.mock("react-i18next", () => ({
  ...jest.requireActual("react-i18next"),
  useTranslation: () => ({
    t: (key: string) => {
      const translations = require("@/locales/en.json") as Record<
        string,
        string
      >;
      return translations[key] ?? key;
    },
  }),
}));

jest.mock(
  "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status",
  () => ({ useGetStorageStatus: jest.fn() }),
);
jest.mock(
  "@/controllers/API/queries/knowledge-base-storage/use-post-storage-retry",
  () => ({ usePostStorageRetry: jest.fn() }),
);

const mockStatus = jest.mocked(useGetStorageStatus);
const mockRetry = jest.mocked(usePostStorageRetry);
const mutate = jest.fn();
let status: StorageUpgradeStatus;

beforeEach(() => {
  jest.clearAllMocks();
  status = {
    is_admin: true,
    running: true,
    revision: "first",
    inventory: { complete: true, issues: 0 },
    stores: [
      {
        kb_id: "kb-id",
        name: "My knowledge",
        storage_state: "migrating",
        phase: "snapshotting",
        migration_id: "migration-id",
        error_code: null,
        can_retry: false,
      },
    ],
  };
  mockStatus.mockImplementation(
    () => ({ data: status }) as ReturnType<typeof useGetStorageStatus>,
  );
  mockRetry.mockReturnValue({
    mutate,
    mutateAsync: jest.fn(),
    reset: jest.fn(),
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    isIdle: true,
    isSuccess: false,
    isPaused: false,
    status: "idle",
    variables: undefined,
    submittedAt: 0,
    failureCount: 0,
    failureReason: null,
    context: undefined,
  });
});

function wrapper(queryClient = new QueryClient()) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

it("names orphaned folders and retries discovery without a migration ID", async () => {
  status = {
    ...status,
    running: false,
    stores: [],
    inventory: {
      complete: false,
      issues: 17,
      storage_directory: "C:/Users/test/.langflow/knowledge_bases",
      details: [
        { source: "former-owner/my-base", code: "missing_source_owner" },
      ],
    },
  };
  const { container, rerender } = render(<StorageUpgradeNotice />, {
    wrapper: wrapper(),
  });
  fireEvent.click(
    screen.getByRole("button", { name: /view upgrade progress/i }),
  );
  expect(
    screen.getByText(status.inventory!.storage_directory!),
  ).toBeInTheDocument();
  expect(screen.getByText("former-owner/my-base")).toBeInTheDocument();
  expect(screen.getByText(/another Langflow database/)).toBeInTheDocument();
  expect(await axe(document.body)).toHaveNoViolations();
  fireEvent.click(screen.getByRole("button", { name: /retry storage check/i }));
  expect(mutate).toHaveBeenCalledWith({ inventory: true }, expect.any(Object));
  act(() => mutate.mock.calls[0][1].onError());
  expect(screen.getByText(/Could not schedule/)).toHaveAttribute(
    "role",
    "alert",
  );
  fireEvent.click(screen.getByRole("button", { name: /retry storage check/i }));
  act(() => mutate.mock.calls[1][1].onSuccess());
  expect(screen.getByText(/Retry scheduled/)).toHaveAttribute("role", "status");
  status = { ...status, inventory: { complete: true, issues: 0 } };
  rerender(<StorageUpgradeNotice />);
  expect(
    container.querySelector('[data-testid="storage-upgrade-notice"]'),
  ).toBeNull();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("explains an unfinished storage check instead of naming earlier folders", () => {
  status = {
    ...status,
    running: false,
    stores: [],
    inventory: {
      complete: false,
      issues: 2,
      storage_directory: "/srv/langflow/knowledge_bases",
      details: [],
      scan_failed: true,
    },
  };
  render(<StorageUpgradeNotice />, { wrapper: wrapper() });
  fireEvent.click(
    screen.getByRole("button", { name: /view upgrade progress/i }),
  );
  expect(
    screen.getByText(/last storage check did not finish/i),
  ).toBeInTheDocument();
  expect(
    screen.queryByText(/another Langflow database/),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("list")).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /retry storage check/i }),
  ).toBeEnabled();
});

it("keeps an empty fresh instance free of storage warnings", () => {
  status = { ...status, running: false, stores: [] };
  render(<StorageUpgradeNotice />, { wrapper: wrapper() });
  expect(
    screen.queryByTestId("storage-upgrade-notice"),
  ).not.toBeInTheDocument();
});

it("offers an inventory retry for older scans without folder details", () => {
  status = {
    ...status,
    running: false,
    stores: [],
    inventory: { complete: false, issues: 1 },
  };
  render(<StorageUpgradeNotice />, { wrapper: wrapper() });
  fireEvent.click(
    screen.getByRole("button", { name: /view upgrade progress/i }),
  );
  expect(
    screen.getByRole("button", { name: /retry storage check/i }),
  ).toBeEnabled();
});

it("disables inventory retries during discovery", () => {
  status = { ...status, inventory: { complete: false, issues: 1 } };
  render(<StorageUpgradeNotice />, { wrapper: wrapper() });
  fireEvent.click(
    screen.getByRole("button", { name: /view upgrade progress/i }),
  );
  expect(
    screen.getByRole("button", { name: /retry storage check/i }),
  ).toBeDisabled();
});

it("shows automatic background progress and source retention from any screen", () => {
  render(<StorageUpgradeNotice />, { wrapper: wrapper() });
  fireEvent.click(
    screen.getByRole("button", { name: /view upgrade progress/i }),
  );
  expect(screen.getByText("Backing up your data")).toBeInTheDocument();
  expect(
    screen.getByText(/without calling your embedding provider/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/become available when the upgrade finishes/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /retry upgrade/i }),
  ).not.toBeInTheDocument();
});

it("gives ordinary users administrator guidance without a retry control", () => {
  status.is_admin = false;
  status.stores[0] = {
    ...status.stores[0],
    storage_state: "needs_attention",
    phase: "needs_attention",
    error_code: "single_host_required",
  };
  render(<StorageUpgradePanel kbId="kb-id" />, { wrapper: wrapper() });
  expect(screen.getByText(/Contact your administrator/)).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /retry upgrade/i }),
  ).not.toBeInTheDocument();
});

it("lets an administrator retry the bound migration and reports scheduling failures", () => {
  status.stores[0] = {
    ...status.stores[0],
    storage_state: "needs_attention",
    phase: "needs_attention",
    error_code: "legacy_workers_running",
    can_retry: true,
  };
  mutate.mockImplementation((_params, options) => options.onError());
  render(<StorageUpgradePanel kbId="kb-id" />, { wrapper: wrapper() });
  expect(
    screen.getByText(/Stop all other Langflow processes on this host/),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /retry upgrade/i }));
  expect(mutate).toHaveBeenCalledWith(
    { migrationId: "migration-id" },
    expect.any(Object),
  );
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Could not schedule the upgrade",
  );
});

it.each(["panel", "dialog"])(
  "acknowledges a retry in the %s even when the same blocker remains",
  (surface) => {
    status.stores[0] = {
      ...status.stores[0],
      storage_state: "needs_attention",
      phase: "needs_attention",
      error_code: "legacy_workers_running",
      can_retry: true,
    };
    mutate.mockImplementation(() => {});
    render(
      surface === "panel" ? (
        <StorageUpgradePanel kbId="kb-id" />
      ) : (
        <StorageUpgradeNotice />
      ),
      { wrapper: wrapper() },
    );
    if (surface === "dialog") {
      fireEvent.click(
        screen.getByRole("button", { name: /view upgrade progress/i }),
      );
    }
    expect(
      screen.getByText(
        "Stop all other Langflow processes on this host, then retry the upgrade. This includes instances using different databases or knowledge directories.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry upgrade/i }));
    act(() => mutate.mock.calls[0][1].onSuccess());
    expect(screen.getByText(/Retry scheduled/)).toHaveAttribute(
      "role",
      "status",
    );
    expect(screen.getByText(/Retry scheduled/)).toHaveTextContent(
      /resolve the issue shown above/,
    );
    expect(
      screen.getByText(/Stop all other Langflow processes on this host/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry upgrade/i }));
    expect(screen.queryByText(/Retry scheduled/)).not.toBeInTheDocument();
    act(() => mutate.mock.calls[1][1].onError());
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Could not schedule the upgrade",
    );
  },
);

it("labels a pending retry and prevents duplicate requests", () => {
  status.stores[0] = {
    ...status.stores[0],
    storage_state: "needs_attention",
    phase: "needs_attention",
    can_retry: true,
  };
  mockRetry.mockReturnValue({
    ...mockRetry(),
    isPending: true,
    isIdle: false,
    isError: false,
    isSuccess: false,
    status: "pending",
    data: undefined,
    error: null,
    variables: { migrationId: "migration-id" },
  });
  render(<StorageUpgradePanel kbId="kb-id" />, { wrapper: wrapper() });
  const button = screen.getByRole("button", { name: /scheduling retry/i });
  expect(button).toBeDisabled();
  fireEvent.click(button);
  expect(mutate).not.toHaveBeenCalled();
});

it.each([
  ["legacy_source_missing", /could be tied to this base/],
  ["legacy_source_ambiguous", /More than one directory/],
])(
  "tells an administrator how to recover a base whose legacy directory is %s",
  (code, guidance) => {
    status.stores[0] = {
      ...status.stores[0],
      storage_state: "needs_attention",
      phase: "needs_attention",
      error_code: code,
      can_retry: true,
    };
    render(<StorageUpgradePanel kbId="kb-id" />, { wrapper: wrapper() });
    expect(screen.getByText(guidance)).toBeInTheDocument();
  },
);

it("refreshes Knowledge and Memory even when a small upgrade completes between polls", () => {
  status.stores = [];
  status.running = false;
  const queryClient = new QueryClient();
  const invalidate = jest.spyOn(queryClient, "invalidateQueries");
  const { rerender } = render(<StorageUpgradeNotice />, {
    wrapper: wrapper(queryClient),
  });
  status = { ...status, revision: "completed" };
  rerender(<StorageUpgradeNotice />);
  expect(invalidate).toHaveBeenCalledWith({
    queryKey: ["useGetKnowledgeBases"],
  });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["useGetMemory"] });
  expect(invalidate).toHaveBeenCalledWith({
    queryKey: ["useGetMemoriesInfinite"],
  });
  expect(
    screen.queryByTestId("storage-upgrade-notice"),
  ).not.toBeInTheDocument();
});

it("closes after completion and does not reopen for later activity", () => {
  const { rerender } = render(<StorageUpgradeNotice />, { wrapper: wrapper() });
  fireEvent.click(
    screen.getByRole("button", { name: /view upgrade progress/i }),
  );
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  const previousStore = status.stores[0];
  status = { ...status, running: false, stores: [], revision: "complete" };
  rerender(<StorageUpgradeNotice />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  status = { ...status, running: true, stores: [previousStore] };
  rerender(<StorageUpgradeNotice />);
  expect(screen.getByTestId("storage-upgrade-notice")).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("lets a viewer dismiss the notice until the availability changes", () => {
  const { rerender } = render(<StorageUpgradeNotice />, { wrapper: wrapper() });
  expect(
    screen.getByRole("region", { name: "Upgrading your data" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(
    screen.queryByTestId("storage-upgrade-notice"),
  ).not.toBeInTheDocument();
  status = { ...status, stores: [{ ...status.stores[0], phase: "importing" }] };
  rerender(<StorageUpgradeNotice />);
  expect(
    screen.queryByTestId("storage-upgrade-notice"),
  ).not.toBeInTheDocument();
  status = {
    ...status,
    running: false,
    stores: [
      {
        ...status.stores[0],
        storage_state: "needs_attention",
        error_code: "validation_failed",
      },
    ],
  };
  rerender(<StorageUpgradeNotice />);
  expect(screen.getByTestId("storage-upgrade-notice")).toBeInTheDocument();
});
