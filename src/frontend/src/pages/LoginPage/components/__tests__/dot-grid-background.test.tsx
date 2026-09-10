import { act, render } from "@testing-library/react";
import DotGridBackground from "../dot-grid-background";

describe("DotGridBackground", () => {
  const context = {
    arc: jest.fn(),
    beginPath: jest.fn(),
    clearRect: jest.fn(),
    fill: jest.fn(),
    fillStyle: "",
    setTransform: jest.fn(),
  };
  const addMediaListener = jest.fn();
  const removeMediaListener = jest.fn();
  let prefersReducedMotion = true;

  beforeEach(() => {
    jest.clearAllMocks();
    prefersReducedMotion = true;
    jest
      .spyOn(HTMLCanvasElement.prototype, "getContext")
      .mockReturnValue(context as unknown as CanvasRenderingContext2D);
    jest.spyOn(window, "requestAnimationFrame").mockReturnValue(1);
    jest.spyOn(window, "cancelAnimationFrame");
    jest.spyOn(window, "matchMedia").mockImplementation(
      (query: string) =>
        ({
          addEventListener: (type, listener) =>
            addMediaListener(query, type, listener),
          matches:
            query === "(prefers-reduced-motion: reduce)" &&
            prefersReducedMotion,
          media: query,
          onchange: null,
          removeEventListener: (type, listener) =>
            removeMediaListener(query, type, listener),
        }) as MediaQueryList,
    );
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("reads the theme once per static draw", () => {
    const getElementById = jest.spyOn(document, "getElementById");

    render(<DotGridBackground />);

    expect(context.arc).toHaveBeenCalled();
    expect(getElementById).toHaveBeenCalledTimes(1);
  });

  it("redraws after resize when reduced motion is enabled", () => {
    render(<DotGridBackground />);
    expect(context.clearRect).toHaveBeenCalledTimes(1);

    act(() => window.dispatchEvent(new Event("resize")));

    expect(context.clearRect).toHaveBeenCalledTimes(2);
    expect(window.requestAnimationFrame).not.toHaveBeenCalled();
  });

  it("sizes the canvas to the layout viewport", () => {
    jest
      .spyOn(document.documentElement, "clientWidth", "get")
      .mockReturnValue(960);
    jest
      .spyOn(document.documentElement, "clientHeight", "get")
      .mockReturnValue(540);

    const { container } = render(<DotGridBackground />);
    const canvas = container.querySelector("canvas");

    expect(canvas).toHaveProperty("width", 960);
    expect(canvas).toHaveProperty("height", 540);
    expect(canvas).toHaveStyle({ width: "960px", height: "540px" });
    expect(context.clearRect).toHaveBeenLastCalledWith(0, 0, 960, 540);
  });

  it("stops and restarts animation when reduced motion changes", () => {
    prefersReducedMotion = false;
    const { unmount } = render(<DotGridBackground />);
    const reducedMotionRegistration = addMediaListener.mock.calls.find(
      ([query]) => query === "(prefers-reduced-motion: reduce)",
    );
    const listener = reducedMotionRegistration?.[2] as (
      event: MediaQueryListEvent,
    ) => void;

    expect(listener).toBeDefined();
    expect(window.requestAnimationFrame).toHaveBeenCalledTimes(1);

    act(() => listener({ matches: true } as MediaQueryListEvent));
    expect(window.cancelAnimationFrame).toHaveBeenCalledWith(1);
    expect(window.requestAnimationFrame).toHaveBeenCalledTimes(1);

    act(() => listener({ matches: false } as MediaQueryListEvent));
    expect(window.requestAnimationFrame).toHaveBeenCalledTimes(2);

    unmount();
    expect(removeMediaListener).toHaveBeenCalledWith(
      "(prefers-reduced-motion: reduce)",
      "change",
      listener,
    );
  });
});
