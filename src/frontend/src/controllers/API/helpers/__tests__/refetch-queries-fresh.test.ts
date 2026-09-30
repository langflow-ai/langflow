import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { refetchQueriesFresh } from "../query-cache";

const FOLDER_KEY = ["useGetFolder", "folder-1", { page: 1 }];
const FILTERS = { queryKey: ["useGetFolder", "folder-1"] };

const flushTimers = (ms: number) =>
  new Promise((resolve) => setTimeout(resolve, ms));

describe("refetchQueriesFresh", () => {
  it("should refetch with the post-mutation rows when the first load is still in flight", async () => {
    const queryClient = new QueryClient();
    const rows = ["existing-flow"];
    let calls = 0;

    const observer = new QueryObserver(queryClient, {
      queryKey: FOLDER_KEY,
      queryFn: () => {
        calls++;
        const snapshot = [...rows];
        return new Promise((resolve) =>
          setTimeout(() => resolve(snapshot), 30),
        );
      },
    });
    const unsubscribe = observer.subscribe(() => {});

    await flushTimers(5);
    rows.push("uploaded-flow");
    await refetchQueriesFresh(queryClient, FILTERS);

    expect(calls).toBe(2);
    expect(queryClient.getQueryData(FOLDER_KEY)).toEqual([
      "existing-flow",
      "uploaded-flow",
    ]);

    unsubscribe();
    queryClient.clear();
  });

  it("should still refetch when no request is in flight", async () => {
    const queryClient = new QueryClient();
    const rows = ["existing-flow"];
    let calls = 0;

    const observer = new QueryObserver(queryClient, {
      queryKey: FOLDER_KEY,
      queryFn: () => {
        calls++;
        return Promise.resolve([...rows]);
      },
    });
    const unsubscribe = observer.subscribe(() => {});

    await flushTimers(5);
    expect(calls).toBe(1);

    rows.push("uploaded-flow");
    await refetchQueriesFresh(queryClient, FILTERS);

    expect(calls).toBe(2);
    expect(queryClient.getQueryData(FOLDER_KEY)).toEqual([
      "existing-flow",
      "uploaded-flow",
    ]);

    unsubscribe();
    queryClient.clear();
  });

  it("should resolve when a cold in-flight request fails", async () => {
    const queryClient = new QueryClient();
    let calls = 0;

    const observer = new QueryObserver(queryClient, {
      queryKey: FOLDER_KEY,
      retry: false,
      queryFn: () => {
        calls++;
        return calls === 1
          ? new Promise((_, reject) =>
              setTimeout(() => reject(new Error("boom")), 30),
            )
          : Promise.resolve(["uploaded-flow"]);
      },
    });
    const unsubscribe = observer.subscribe(() => {});

    await flushTimers(5);
    await refetchQueriesFresh(queryClient, FILTERS);

    expect(calls).toBe(2);
    expect(queryClient.getQueryData(FOLDER_KEY)).toEqual(["uploaded-flow"]);

    unsubscribe();
    queryClient.clear();
  });
});
