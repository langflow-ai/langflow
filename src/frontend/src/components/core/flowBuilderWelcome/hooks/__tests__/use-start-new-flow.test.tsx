import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { useStartNewFlow } from "../use-start-new-flow";

const addFlow = jest.fn();
const navigate = jest.fn();
const openWelcome = jest.fn();

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => addFlow,
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => navigate,
}));

jest.mock("@/stores/flowBuilderWelcomeStore", () => ({
  __esModule: true,
  default: (selector: (state: { open: jest.Mock }) => unknown) =>
    selector({ open: openWelcome }),
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <MemoryRouter initialEntries={["/all"]}>{children}</MemoryRouter>
);

// The real router navigation, so the hook sees the location change.
function useStartNewFlowWithRouter() {
  return { start: useStartNewFlow(), routerNavigate: useNavigate() };
}

describe("useStartNewFlow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    addFlow.mockReset();
  });

  it("creates one flow and opens it when clicked again while creating", async () => {
    let finishCreate: (id: string) => void = () => {};
    addFlow.mockReturnValue(
      new Promise<string>((resolve) => {
        finishCreate = resolve;
      }),
    );
    const { result } = renderHook(() => useStartNewFlow(), { wrapper });

    let firstClick: Promise<void> = Promise.resolve();
    await act(async () => {
      firstClick = result.current();
      void result.current();
    });
    await act(async () => {
      finishCreate("flow-1");
      await firstClick;
    });

    expect(addFlow).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith("/flow/flow-1");
    expect(openWelcome).toHaveBeenCalledWith("flow-1");
  });

  it("ignores a click after the create while the route has not changed", async () => {
    addFlow.mockResolvedValue("flow-1");
    const { result } = renderHook(() => useStartNewFlow(), { wrapper });

    await act(async () => {
      await result.current();
      await result.current();
    });

    expect(addFlow).toHaveBeenCalledTimes(1);
  });

  it("creates again after a failed create", async () => {
    addFlow
      .mockRejectedValueOnce(new Error("create failed"))
      .mockResolvedValueOnce("flow-2");
    const { result } = renderHook(() => useStartNewFlow(), { wrapper });

    await act(async () => {
      await expect(result.current()).rejects.toThrow("create failed");
    });
    await act(async () => {
      await result.current();
    });

    expect(addFlow).toHaveBeenCalledTimes(2);
    expect(navigate).toHaveBeenCalledWith("/flow/flow-2");
  });

  it("creates again once the route has changed", async () => {
    addFlow.mockResolvedValueOnce("flow-1").mockResolvedValueOnce("flow-2");
    const { result } = renderHook(() => useStartNewFlowWithRouter(), {
      wrapper,
    });

    await act(async () => {
      await result.current.start();
    });
    act(() => result.current.routerNavigate("/all/folder/other"));
    await act(async () => {
      await result.current.start();
    });

    expect(addFlow).toHaveBeenCalledTimes(2);
  });
});
