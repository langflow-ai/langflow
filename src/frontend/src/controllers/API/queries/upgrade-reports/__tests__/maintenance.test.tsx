import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { api } from "@/controllers/API/api";
import { useMigrationPauseQuery } from "@/controllers/API/queries/migration";
import { useUpgradeMaintenance } from "..";

afterEach(() => jest.restoreAllMocks());

it("shares a recent status read between the global notice and upgrade controls", async () => {
  const get = jest.spyOn(api, "get").mockResolvedValue({
    data: {
      paused: false,
      maintenance: false,
      migration: false,
      running_jobs: 0,
    },
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  const notice = renderHook(() => useMigrationPauseQuery(), { wrapper });
  await waitFor(() => expect(notice.result.current.isSuccess).toBe(true));

  const upgrade = renderHook(() => useUpgradeMaintenance(), { wrapper });
  await waitFor(() => expect(upgrade.result.current.isSuccess).toBe(true));

  expect(get).toHaveBeenCalledTimes(1);
  expect(upgrade.result.current.data).toEqual(notice.result.current.data);
});
