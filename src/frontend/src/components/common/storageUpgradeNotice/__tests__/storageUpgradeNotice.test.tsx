import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { StorageUpgradeStatus } from "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status";
import { useGetStorageStatus } from "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status";
import { usePostStorageRetry } from "@/controllers/API/queries/knowledge-base-storage/use-post-storage-retry";
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
    screen.getByText(/Stop the other Langflow instance/),
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
