import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import {
  MemoryRouter,
  type NavigateFunction,
  useNavigate,
} from "react-router-dom";
import { getMessages } from "@/controllers/API/queries/messages/use-get-messages";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useSessionManagerStore } from "@/stores/sessionManagerStore";
import usePlaygroundDeepLink from "../use-playground-deep-link";

jest.mock("@/controllers/API/queries/messages/use-get-messages", () => ({
  getMessages: jest.fn(),
}));

const mockGetMessages = jest.mocked(getMessages);
const FLOW_ID = "flow-1";
const savedMessage = {
  data: [
    {
      id: "message-1",
      flow_id: FLOW_ID,
      session_id: "run-1",
      text: "Saved message",
      sender: "User",
      sender_name: "User",
      timestamp: "2026-10-23 12:00:00",
      files: [],
      edit: false,
      background_color: "",
      text_color: "",
    },
  ],
};

function renderDeepLink(
  url = "/flow/flow-1?playground=true&session=run-1",
  flowId: string | null = FLOW_ID,
  strict = false,
) {
  let navigate: NavigateFunction;
  function Navigation({ children }: PropsWithChildren) {
    navigate = useNavigate();
    return children;
  }
  function Wrapper({ children }: PropsWithChildren) {
    return (
      <MemoryRouter initialEntries={[url]}>
        <Navigation>{children}</Navigation>
      </MemoryRouter>
    );
  }
  const hook = renderHook(
    (props: { routeFlowId: string; flowId?: string; hasChat: boolean }) =>
      usePlaygroundDeepLink(props),
    {
      wrapper: Wrapper,
      reactStrictMode: strict,
      initialProps: {
        routeFlowId: FLOW_ID,
        flowId: flowId ?? undefined,
        hasChat: true,
      },
    },
  );
  return {
    ...hook,
    navigate: (url: string) => act(() => navigate(url)),
  };
}

function deferredResponse() {
  let resolve!: (value: Awaited<ReturnType<typeof getMessages>>) => void;
  const promise = new Promise<Awaited<ReturnType<typeof getMessages>>>(
    (res) => {
      resolve = res;
    },
  );
  return { promise, resolve };
}

describe("Playground deep links", () => {
  beforeEach(() => {
    jest.resetAllMocks();
    usePlaygroundStore.getState().reset();
    useSessionManagerStore.getState().reset();
    mockGetMessages.mockResolvedValue(savedMessage);
  });

  it("should open the Playground and select a saved session outside loaded pages", async () => {
    renderDeepLink();

    await waitFor(() =>
      expect(useSessionManagerStore.getState().activeSessionId).toBe("run-1"),
    );
    expect(usePlaygroundStore.getState()).toMatchObject({
      isOpen: true,
      isFullscreen: true,
    });
    expect(mockGetMessages).toHaveBeenCalledWith(FLOW_ID, {
      session_id: "run-1",
      limit: 1,
    });
    expect(useSessionManagerStore.getState().sessions).toContainEqual({
      id: "run-1",
      isLocal: false,
    });

    act(() => useSessionManagerStore.getState().syncFromServer(["recent"]));
    expect(useSessionManagerStore.getState().getOrderedSessionIds()).toContain(
      "run-1",
    );
  });

  it.each(["", "&session=", "&session=flow-1"])(
    "should open the default session without a lookup for %s",
    (session) => {
      renderDeepLink(`/flow/flow-1?playground=true${session}`);

      expect(usePlaygroundStore.getState().isOpen).toBe(true);
      expect(useSessionManagerStore.getState().activeSessionId).toBe(FLOW_ID);
      expect(mockGetMessages).not.toHaveBeenCalled();
    },
  );

  it.each(["", "?session=run-1", "?playground=false&session=run-1"])(
    "should leave the Playground unchanged without an explicit open request: %s",
    (search) => {
      renderDeepLink(`/flow/flow-1${search}`);

      expect(usePlaygroundStore.getState().isOpen).toBe(false);
      expect(mockGetMessages).not.toHaveBeenCalled();
    },
  );

  it("should wait for the requested flow to finish loading", async () => {
    const hook = renderDeepLink(undefined, "previous-flow");

    expect(usePlaygroundStore.getState().isOpen).toBe(false);
    expect(mockGetMessages).not.toHaveBeenCalled();
    hook.rerender({ routeFlowId: FLOW_ID, flowId: FLOW_ID, hasChat: true });

    await waitFor(() =>
      expect(useSessionManagerStore.getState().activeSessionId).toBe("run-1"),
    );
  });

  it("should wait for chat components before opening", () => {
    const hook = renderDeepLink(undefined, null);
    hook.rerender({ routeFlowId: FLOW_ID, flowId: FLOW_ID, hasChat: false });

    expect(usePlaygroundStore.getState().isOpen).toBe(false);
    expect(mockGetMessages).not.toHaveBeenCalled();

    hook.rerender({ routeFlowId: FLOW_ID, flowId: FLOW_ID, hasChat: true });
    expect(usePlaygroundStore.getState().isOpen).toBe(true);
  });

  it("should keep the normal session when the requested one does not exist", async () => {
    mockGetMessages.mockResolvedValue({ data: [] });
    renderDeepLink();

    await act(async () => {});

    expect(usePlaygroundStore.getState().isOpen).toBe(true);
    expect(useSessionManagerStore.getState().activeSessionId).toBe(FLOW_ID);
    expect(useSessionManagerStore.getState().sessions).toEqual([]);
  });

  it("should keep the normal session when the lookup fails", async () => {
    mockGetMessages.mockRejectedValue(new Error("Unavailable"));
    renderDeepLink();

    await act(async () => {});

    expect(usePlaygroundStore.getState().isOpen).toBe(true);
    expect(useSessionManagerStore.getState().activeSessionId).toBe(FLOW_ID);
  });

  it("should decode session names from the URL once", async () => {
    renderDeepLink("/flow/flow-1?playground=true&session=run%20%26%20%2B%25");

    await waitFor(() =>
      expect(useSessionManagerStore.getState().activeSessionId).toBe(
        "run & +%",
      ),
    );
    expect(mockGetMessages).toHaveBeenCalledWith(FLOW_ID, {
      session_id: "run & +%",
      limit: 1,
    });
  });

  it("should not override a manual selection with a delayed response", async () => {
    const pending = deferredResponse();
    mockGetMessages.mockReturnValue(pending.promise);
    renderDeepLink();

    act(() => useSessionManagerStore.getState().setActiveSessionId("manual"));
    await act(async () => pending.resolve(savedMessage));

    expect(useSessionManagerStore.getState().activeSessionId).toBe("manual");
    expect(useSessionManagerStore.getState().sessions).toEqual([]);
  });

  it("should ignore an old lookup after a different deep link is opened", async () => {
    const pending = deferredResponse();
    mockGetMessages.mockReturnValueOnce(pending.promise);
    const hook = renderDeepLink();

    hook.navigate("/flow/flow-1?playground=true&session=run-2");
    await waitFor(() =>
      expect(useSessionManagerStore.getState().activeSessionId).toBe("run-2"),
    );
    await act(async () => pending.resolve(savedMessage));

    expect(useSessionManagerStore.getState().activeSessionId).toBe("run-2");
  });

  it("should ignore a response after leaving the flow", async () => {
    const pending = deferredResponse();
    mockGetMessages.mockReturnValue(pending.promise);
    const hook = renderDeepLink();

    hook.rerender({ routeFlowId: "flow-2", flowId: FLOW_ID, hasChat: true });
    useSessionManagerStore.getState().initialize("flow-2");
    await act(async () => pending.resolve(savedMessage));

    expect(useSessionManagerStore.getState().activeSessionId).toBe("flow-2");
  });

  it("should ignore a response after unmount", async () => {
    const pending = deferredResponse();
    mockGetMessages.mockReturnValue(pending.promise);
    const hook = renderDeepLink();
    hook.unmount();

    await act(async () => pending.resolve(savedMessage));

    expect(useSessionManagerStore.getState().activeSessionId).toBe(FLOW_ID);
  });

  it("should ignore a pending selection after the Playground is closed", async () => {
    const pending = deferredResponse();
    mockGetMessages.mockReturnValue(pending.promise);
    renderDeepLink();

    act(() => usePlaygroundStore.getState().setIsOpen(false));
    await act(async () => pending.resolve(savedMessage));

    expect(useSessionManagerStore.getState().activeSessionId).toBe(FLOW_ID);
    expect(usePlaygroundStore.getState().isOpen).toBe(false);
  });

  it("should cancel the pending selection when the URL no longer requests it", async () => {
    const pending = deferredResponse();
    mockGetMessages.mockReturnValue(pending.promise);
    const hook = renderDeepLink();

    hook.navigate("/flow/flow-1");
    await act(async () => pending.resolve(savedMessage));

    expect(useSessionManagerStore.getState().activeSessionId).toBe(FLOW_ID);
    expect(useSessionManagerStore.getState().sessions).toEqual([]);
  });

  it("should preserve manual closing and selection on unrelated rerenders", async () => {
    const hook = renderDeepLink();
    await waitFor(() =>
      expect(useSessionManagerStore.getState().activeSessionId).toBe("run-1"),
    );

    act(() => {
      usePlaygroundStore.getState().setIsOpen(false);
      useSessionManagerStore.getState().setActiveSessionId("manual");
    });
    hook.navigate("/flow/flow-1?playground=true&session=run-1&other=value");

    expect(usePlaygroundStore.getState().isOpen).toBe(false);
    expect(useSessionManagerStore.getState().activeSessionId).toBe("manual");
    expect(mockGetMessages).toHaveBeenCalledTimes(1);
  });

  it("should finish selecting the session under Strict Mode effect replay", async () => {
    renderDeepLink(undefined, FLOW_ID, true);

    await waitFor(() =>
      expect(useSessionManagerStore.getState().activeSessionId).toBe("run-1"),
    );
    expect(mockGetMessages).toHaveBeenCalledTimes(1);
  });
});
