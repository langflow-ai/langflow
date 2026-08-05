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

const RouterWrapper = ({ children }: PropsWithChildren) =>
  createElement(
    MemoryRouter,
    {
      future: {
        v7_relativeSplatPath: true,
        v7_startTransition: true,
      },
    },
    children,
  );

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
