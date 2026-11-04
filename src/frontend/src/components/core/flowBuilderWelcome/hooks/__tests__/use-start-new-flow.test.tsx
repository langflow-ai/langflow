/**
 * Tests for the "New Flow" entry point: a second click while the first create
 * is in flight must not create a second flow.
 */

import { act, renderHook } from "@testing-library/react";
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

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: "project-1" }),
}));

jest.mock("@/stores/flowBuilderWelcomeStore", () => ({
  __esModule: true,
  default: (selector: (state: { open: jest.Mock }) => unknown) =>
    selector({ open: openWelcome }),
}));

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
    const { result } = renderHook(() => useStartNewFlow());

    let firstClick: Promise<void> = Promise.resolve();
    await act(async () => {
      firstClick = result.current();
      void result.current();
    });
    expect(addFlow).toHaveBeenCalledTimes(1);

    await act(async () => {
      finishCreate("flow-1");
      await firstClick;
    });
    expect(openWelcome).toHaveBeenCalledWith("flow-1");
    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith("/flow/flow-1/folder/project-1");
  });

  it("allows another try after a failed create", async () => {
    addFlow.mockRejectedValueOnce(new Error("create failed"));
    addFlow.mockResolvedValueOnce("flow-2");
    const { result } = renderHook(() => useStartNewFlow());

    await act(async () => {
      await expect(result.current()).rejects.toThrow("create failed");
    });
    expect(navigate).not.toHaveBeenCalled();

    await act(async () => {
      await result.current();
    });
    expect(addFlow).toHaveBeenCalledTimes(2);
    expect(navigate).toHaveBeenCalledWith("/flow/flow-2/folder/project-1");
  });
});
