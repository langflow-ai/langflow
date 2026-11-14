import { act, renderHook } from "@testing-library/react";
import { useTypingEffect } from "../use-typing-effect";

const hasLoneSurrogate = (value: string) =>
  /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(
    value,
  );

function typeOut(text: string): string[] {
  const { result } = renderHook(() =>
    useTypingEffect({ text, willAnimate: true, canStart: true }),
  );
  const frames: string[] = [];
  for (let tick = 0; tick <= text.length; tick++) {
    act(() => {
      jest.advanceTimersByTime(30);
    });
    frames.push(result.current.displayedText);
  }
  return frames;
}

describe("useTypingEffect", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("should_include_the_whole_emoji_when_a_tick_lands_inside_a_surrogate_pair", () => {
    const frames = typeOut("ab😀");

    expect(frames[0]).toBe("ab😀");
  });

  it("should_never_show_a_lone_surrogate_when_typing_emoji_sequences", () => {
    const text = "Hi 👩‍👩‍👧 from 🇧🇷 and 👍🏽 done 😀😀😀";

    const frames = typeOut(text);

    for (const frame of frames) {
      expect(hasLoneSurrogate(frame)).toBe(false);
    }
    expect(frames.at(-1)).toBe(text);
  });

  it("should_type_three_characters_per_tick_when_the_text_is_plain", () => {
    const frames = typeOut("abcdefg");

    expect(frames.slice(0, 3)).toEqual(["abc", "abcdef", "abcdefg"]);
  });
});
