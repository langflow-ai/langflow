import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { refetchQueriesFresh } from "../query-cache";

const FOLDER_KEY = ["useGetFolder", "folder-1", { page: 1 }];
const FILTERS = { queryKey: ["useGetFolder", "folder-1"] };

const deferred = <T>() => {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

describe("refetchQueriesFresh", () => {
  it("should refetch with the post-mutation rows when the first load is still in flight", async () => {
    const queryClient = new QueryClient();
    const rows = ["existing-flow"];
    let calls = 0;
    const requestStarted = deferred<void>();
    const firstRequest = deferred<string[]>();

    const observer = new QueryObserver(queryClient, {
      queryKey: FOLDER_KEY,
      queryFn: () => {
        calls++;
        const snapshot = [...rows];
        if (calls === 1) {
          requestStarted.resolve();
          return firstRequest.promise;
        }
        return Promise.resolve(snapshot);
      },
    });
    const unsubscribe = observer.subscribe(() => {});

    await requestStarted.promise;
    rows.push("uploaded-flow");
    const refetchPromise = refetchQueriesFresh(queryClient, FILTERS);
    firstRequest.resolve(["existing-flow"]);
    await refetchPromise;

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
    const requestStarted = deferred<void>();

    const observer = new QueryObserver(queryClient, {
      queryKey: FOLDER_KEY,
      queryFn: () => {
        calls++;
        requestStarted.resolve();
        return Promise.resolve([...rows]);
      },
    });
    const unsubscribe = observer.subscribe(() => {});

    await requestStarted.promise;
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
    const requestStarted = deferred<void>();
    const firstRequest = deferred<string[]>();

    const observer = new QueryObserver(queryClient, {
      queryKey: FOLDER_KEY,
      retry: false,
      queryFn: () => {
        calls++;
        if (calls === 1) {
          requestStarted.resolve();
          return firstRequest.promise;
        }
        return Promise.resolve(["uploaded-flow"]);
      },
    });
    const unsubscribe = observer.subscribe(() => {});

    await requestStarted.promise;
    const refetchPromise = refetchQueriesFresh(queryClient, FILTERS);
    firstRequest.reject(new Error("boom"));
    await refetchPromise;

    expect(calls).toBe(2);
    expect(queryClient.getQueryData(FOLDER_KEY)).toEqual(["uploaded-flow"]);

    unsubscribe();
    queryClient.clear();
  });
});
