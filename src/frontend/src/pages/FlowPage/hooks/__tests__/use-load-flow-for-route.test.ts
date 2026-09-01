import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type PropsWithChildren } from "react";
import { MemoryRouter } from "react-router-dom";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import type { FlowType } from "@/types/flow";
import useLoadFlowForRoute from "../use-load-flow-for-route";

const FLOW: FlowType = {
  id: "new-flow",
  name: "New Flow",
  description: "",
  data: null,
};

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
};

const deferred = <T>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

// react-router v7 makes the former v7_relativeSplatPath / v7_startTransition
// opt-ins the default behavior, so the `future` prop no longer exists.
const RouterWrapper = ({ children }: PropsWithChildren) =>
  createElement(MemoryRouter, null, children);

const renderRouteLoader = (
  options: {
    id?: string;
    getFlow?: jest.Mock<Promise<FlowType>, [{ id: string }]>;
  } = {},
) => {
  const id = "id" in options ? options.id : FLOW.id;
  const getFlow = options.getFlow ?? jest.fn().mockResolvedValue(FLOW);
  const applyFlowToCanvas = jest.fn();
  const navigate = jest.fn();
  const result = renderHook(() =>
    useLoadFlowForRoute({
      id,
      flows: [],
      currentFlowId: "",
      types: { flow: "Flow" },
      getFlow,
      applyFlowToCanvas,
      navigate,
    }),
  );

  return { ...result, getFlow, applyFlowToCanvas, navigate };
};

describe("useLoadFlowForRoute", () => {
  let consoleError: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it("confirms a store-missing flow with the server and applies it", async () => {
    const { getFlow, applyFlowToCanvas, navigate } = renderRouteLoader();

    await waitFor(() => {
      expect(getFlow).toHaveBeenCalledWith({ id: FLOW.id });
      expect(applyFlowToCanvas).toHaveBeenCalledWith(FLOW);
    });
    expect(navigate).not.toHaveBeenCalled();
  });

  it("does not restart a pending load when the parent rerenders", async () => {
    const pending = deferred<FlowType>();
    const getFlow = jest.fn().mockReturnValue(pending.promise);
    const applyFlowToCanvas = jest.fn();
    const flows: FlowType[] = [];
    const types = { flow: "Flow" };

    const { rerender } = renderHook(
      () => {
        const navigate = useCustomNavigate();
        useLoadFlowForRoute({
          id: FLOW.id,
          flows,
          currentFlowId: "",
          types,
          getFlow,
          applyFlowToCanvas,
          navigate,
        });
      },
      { wrapper: RouterWrapper },
    );

    await waitFor(() => expect(getFlow).toHaveBeenCalledTimes(1));
    Array.from({ length: 5 }).forEach(() => rerender());

    expect(getFlow).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(FLOW));
    expect(applyFlowToCanvas).toHaveBeenCalledWith(FLOW);
  });

  it("fires a single request when the navigate identity changes every render", async () => {
    const pending = deferred<FlowType>();
    const getFlow = jest.fn().mockReturnValue(pending.promise);
    const applyFlowToCanvas = jest.fn();
    const flows: FlowType[] = [];
    const types = { flow: "Flow" };

    const { rerender } = renderHook(() =>
      useLoadFlowForRoute({
        id: FLOW.id,
        flows,
        currentFlowId: "",
        types,
        getFlow,
        applyFlowToCanvas,
        // An unmemoized navigate is what turned this effect into a request
        // storm: a new identity per render re-ran it while the first response
        // was still in flight.
        navigate: () => {},
      }),
    );

    await waitFor(() => expect(getFlow).toHaveBeenCalledTimes(1));
    Array.from({ length: 20 }).forEach(() => rerender());

    expect(getFlow).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve(FLOW));
    expect(applyFlowToCanvas).toHaveBeenCalledTimes(1);
  });

  it("requests the new id exactly once when the route changes flow", async () => {
    const otherFlow: FlowType = { ...FLOW, id: "other-flow" };
    const getFlow = jest
      .fn()
      .mockImplementation(({ id }: { id: string }) =>
        Promise.resolve(id === FLOW.id ? FLOW : otherFlow),
      );
    const applyFlowToCanvas = jest.fn();
    const flows: FlowType[] = [];
    const types = { flow: "Flow" };

    const { rerender } = renderHook(
      ({ id }: { id: string }) =>
        useLoadFlowForRoute({
          id,
          flows,
          currentFlowId: "",
          types,
          getFlow,
          applyFlowToCanvas,
          navigate: () => {},
        }),
      { initialProps: { id: FLOW.id } },
    );

    await waitFor(() => expect(getFlow).toHaveBeenCalledWith({ id: FLOW.id }));

    rerender({ id: otherFlow.id });

    await waitFor(() =>
      expect(getFlow).toHaveBeenCalledWith({ id: otherFlow.id }),
    );
    Array.from({ length: 10 }).forEach(() => rerender({ id: otherFlow.id }));

    expect(getFlow).toHaveBeenCalledTimes(2);
  });

  it("ignores an older request after revisiting the same flow id", async () => {
    const firstFlowRequest = deferred<FlowType>();
    const otherFlowRequest = deferred<FlowType>();
    const secondFlowRequest = deferred<FlowType>();
    const otherFlow: FlowType = { ...FLOW, id: "other-flow" };
    const error = new Error("older request failed");
    const getFlow = jest
      .fn()
      .mockReturnValueOnce(firstFlowRequest.promise)
      .mockReturnValueOnce(otherFlowRequest.promise)
      .mockReturnValueOnce(secondFlowRequest.promise);
    const applyFlowToCanvas = jest.fn();
    const navigate = jest.fn();
    const flows: FlowType[] = [];
    const types = { flow: "Flow" };

    const { rerender } = renderHook(
      ({ id }: { id: string }) =>
        useLoadFlowForRoute({
          id,
          flows,
          currentFlowId: "",
          types,
          getFlow,
          applyFlowToCanvas,
          navigate,
        }),
      { initialProps: { id: FLOW.id } },
    );

    await waitFor(() => expect(getFlow).toHaveBeenCalledTimes(1));
    rerender({ id: otherFlow.id });
    await waitFor(() => expect(getFlow).toHaveBeenCalledTimes(2));
    rerender({ id: FLOW.id });
    await waitFor(() => expect(getFlow).toHaveBeenCalledTimes(3));

    await act(async () => secondFlowRequest.resolve(FLOW));
    expect(applyFlowToCanvas).toHaveBeenCalledWith(FLOW);

    await act(async () => firstFlowRequest.reject(error));
    expect(navigate).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
  });

  it("allows a retry after a failed confirmation", async () => {
    const error = new Error("network unavailable");
    const getFlow = jest
      .fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue(FLOW);
    const applyFlowToCanvas = jest.fn();
    const flows: FlowType[] = [];
    const types = { flow: "Flow" };

    const { rerender } = renderHook(() =>
      useLoadFlowForRoute({
        id: FLOW.id,
        flows,
        currentFlowId: "",
        types,
        getFlow,
        applyFlowToCanvas,
        navigate: () => {},
      }),
    );

    await waitFor(() => expect(getFlow).toHaveBeenCalledTimes(1));

    rerender();

    await waitFor(() => expect(applyFlowToCanvas).toHaveBeenCalledWith(FLOW));
    expect(getFlow).toHaveBeenCalledTimes(2);
  });

  it("logs and redirects when the server cannot confirm the flow", async () => {
    const error = new Error("network unavailable");
    const getFlow = jest.fn().mockRejectedValue(error);
    const { applyFlowToCanvas, navigate } = renderRouteLoader({ getFlow });

    await waitFor(() => {
      expect(consoleError).toHaveBeenCalledWith(
        `Failed to confirm flow ${FLOW.id} from the server:`,
        error,
      );
      expect(navigate).toHaveBeenCalledWith("/all");
    });
    expect(applyFlowToCanvas).not.toHaveBeenCalled();
  });

  it("redirects without fetching when the route id is missing", async () => {
    const getFlow = jest.fn().mockResolvedValue(FLOW);
    const { navigate } = renderRouteLoader({ id: undefined, getFlow });

    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/all"));
    expect(getFlow).not.toHaveBeenCalled();
  });

  it("does not apply a flow when the effect is cleaned up", async () => {
    const pending = deferred<FlowType>();
    const getFlow = jest.fn().mockReturnValue(pending.promise);
    const { unmount, applyFlowToCanvas, navigate } = renderRouteLoader({
      getFlow,
    });

    await waitFor(() => expect(getFlow).toHaveBeenCalledWith({ id: FLOW.id }));
    unmount();
    await act(async () => pending.resolve(FLOW));

    expect(applyFlowToCanvas).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("does not redirect or log when a stale confirmation fails", async () => {
    const pending = deferred<FlowType>();
    const getFlow = jest.fn().mockReturnValue(pending.promise);
    const { unmount, navigate } = renderRouteLoader({ getFlow });

    await waitFor(() => expect(getFlow).toHaveBeenCalledWith({ id: FLOW.id }));
    unmount();
    await act(async () => pending.reject(new Error("stale request failed")));

    expect(navigate).not.toHaveBeenCalled();
    expect(consoleError).not.toHaveBeenCalled();
  });
});
