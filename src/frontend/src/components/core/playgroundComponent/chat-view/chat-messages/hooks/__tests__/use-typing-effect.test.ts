import { act, renderHook } from "@testing-library/react";
import { useTypingEffect } from "../use-typing-effect";

describe("useTypingEffect", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("keeps surrogate pairs intact in intermediate frames", () => {
    const { result } = renderHook(() =>
      useTypingEffect({
        text: "ab😀",
        willAnimate: true,
        canStart: true,
      }),
    );

    act(() => {
      jest.advanceTimersByTime(30);
    });

    expect(result.current.displayedText).toBe("ab😀");
  });
});
