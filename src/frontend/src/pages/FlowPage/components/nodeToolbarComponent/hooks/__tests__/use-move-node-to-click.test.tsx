import { act, renderHook } from "@testing-library/react";
import { useMoveNodeToClick } from "../use-move-node-to-click";

const screenToFlowPosition = jest.fn((p: { x: number; y: number }) => p);
jest.mock("@xyflow/react", () => ({
  useReactFlow: () => ({ screenToFlowPosition }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const takeSnapshot = jest.fn();
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ takeSnapshot }),
}));

const setNoticeData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setNoticeData }),
}));

const setNode = jest.fn();
const autoSaveFlow = jest.fn();
const updateCurrentFlow = jest.fn();
const storeState = {
  nodes: [
    {
      id: "node-1",
      position: { x: 0, y: 0 },
      measured: { width: 100, height: 60 },
    },
  ],
  setNode,
  autoSaveFlow,
  updateCurrentFlow,
};
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: { getState: () => storeState },
}));

function pane() {
  const el = document.createElement("div");
  el.className = "react-flow__pane";
  document.body.appendChild(el);
  return el;
}

function pointerDownOn(el: Element, x = 300, y = 200) {
  const event = new Event("pointerdown", {
    bubbles: true,
    cancelable: true,
  }) as PointerEvent;
  Object.defineProperty(event, "clientX", { value: x });
  Object.defineProperty(event, "clientY", { value: y });
  el.dispatchEvent(event);
}

describe("useMoveNodeToClick", () => {
  afterEach(() => {
    document.body.innerHTML = "";
    jest.clearAllMocks();
  });

  it("places the node centered on the clicked pane position, snapshots first, and persists", () => {
    const paneEl = pane();
    const { result } = renderHook(() => useMoveNodeToClick("node-1"));
    act(() => result.current());
    expect(setNoticeData).toHaveBeenCalledWith({
      title: "nodeToolbar.moveToArmed",
    });

    act(() => pointerDownOn(paneEl, 300, 200));

    expect(takeSnapshot).toHaveBeenCalledTimes(1);
    expect(setNode).toHaveBeenCalledTimes(1);
    const [id, updater] = setNode.mock.calls[0];
    expect(id).toBe("node-1");
    expect(updater(storeState.nodes[0]).position).toEqual({ x: 250, y: 170 });
    expect(autoSaveFlow).toHaveBeenCalledTimes(1);
    expect(updateCurrentFlow).toHaveBeenCalledTimes(1);
  });

  it("is a one-shot gesture: a second pane click does nothing", () => {
    const paneEl = pane();
    const { result } = renderHook(() => useMoveNodeToClick("node-1"));
    act(() => result.current());
    act(() => pointerDownOn(paneEl));
    act(() => pointerDownOn(paneEl));
    expect(setNode).toHaveBeenCalledTimes(1);
  });

  it("cancels on a click that is not on the pane", () => {
    pane();
    const other = document.createElement("button");
    document.body.appendChild(other);
    const { result } = renderHook(() => useMoveNodeToClick("node-1"));
    act(() => result.current());
    act(() => pointerDownOn(other));
    expect(setNode).not.toHaveBeenCalled();
    // and the gesture is disarmed — a later pane click must not fire either
    act(() => pointerDownOn(document.querySelector(".react-flow__pane")!));
    expect(setNode).not.toHaveBeenCalled();
  });

  it("cancels on Escape", () => {
    const paneEl = pane();
    const { result } = renderHook(() => useMoveNodeToClick("node-1"));
    act(() => result.current());
    act(() => {
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
    });
    act(() => pointerDownOn(paneEl));
    expect(setNode).not.toHaveBeenCalled();
  });

  it("restores the pane cursor when disarmed", () => {
    const paneEl = pane();
    const { result } = renderHook(() => useMoveNodeToClick("node-1"));
    act(() => result.current());
    expect(paneEl.style.cursor).toBe("crosshair");
    act(() => pointerDownOn(paneEl));
    expect(paneEl.style.cursor).toBe("");
  });
});
