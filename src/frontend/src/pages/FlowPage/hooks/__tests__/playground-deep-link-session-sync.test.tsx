import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { MemoryRouter } from "react-router-dom";
import { useSessionManager } from "@/components/core/playgroundComponent/hooks/use-session-manager";
import { useSessionManagerStore } from "@/stores/sessionManagerStore";
import usePlaygroundDeepLink from "../use-playground-deep-link";

const mockGet = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}));
jest.mock("@/stores/flowStore", () => {
  const state = { playgroundPage: false };
  return {
    __esModule: true,
    default: Object.assign(
      (selector: (s: typeof state) => unknown) => selector(state),
      { getState: () => state },
    ),
  };
});

const FLOW_ID = "flow-1";

describe("Playground deep links with the paged session manager", () => {
  beforeEach(() => {
    mockGet.mockReset();
    useSessionManagerStore.getState().reset();
  });

  it("should keep a linked older session when the first session page arrives later", async () => {
    let resolvePage!: (response: { data: string[] }) => void;
    const page = new Promise<{ data: string[] }>((resolve) => {
      resolvePage = resolve;
    });
    mockGet.mockImplementation(async (url: string) => {
      if (url.endsWith("/sessions")) return page;
      return { data: [{ session_id: "old-run", flow_id: FLOW_ID }] };
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={["/flow/flow-1?playground=true&session=old-run"]}
        >
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
    const hook = renderHook(
      () => {
        const manager = useSessionManager({ flowId: FLOW_ID });
        usePlaygroundDeepLink({
          routeFlowId: FLOW_ID,
          flowId: FLOW_ID,
          hasChat: true,
        });
        return manager;
      },
      { wrapper },
    );

    await waitFor(() =>
      expect(hook.result.current.activeSessionId).toBe("old-run"),
    );
    await act(async () =>
      resolvePage({
        data: Array.from({ length: 101 }, (_, i) => `recent-${i}`),
      }),
    );
    await waitFor(() =>
      expect(hook.result.current.sessionsPagination.isSuccess).toBe(true),
    );

    expect(hook.result.current.activeSessionId).toBe("old-run");
    expect(hook.result.current.sessions).toContain("old-run");
    expect(hook.result.current.sessionsPagination.hasNextPage).toBe(true);
    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(mockGet).toHaveBeenCalledWith(
      expect.not.stringContaining("/sessions"),
      {
        params: { flow_id: FLOW_ID, session_id: "old-run", limit: 1 },
      },
    );

    hook.unmount();
    queryClient.clear();
  });
});
