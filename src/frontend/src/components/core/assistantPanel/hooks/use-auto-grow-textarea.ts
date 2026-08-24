import { useLayoutEffect } from "react";

/**
 * Grow a composer textarea with its content, up to ``maxHeightPx``.
 *
 * The composer sits at the bottom of a fixed-height surface, so it cannot grow without bound —
 * past the cap the draft scrolls inside the box and the conversation above stays readable.
 */
export function useAutoGrowTextarea(
  ref: React.RefObject<HTMLTextAreaElement | null>,
  value: string,
  maxHeightPx: number,
) {
  useLayoutEffect(() => {
    const textarea = ref.current;
    if (!textarea) return;
    // Collapse first so the measured scrollHeight reflects the content, not the previous height.
    textarea.style.height = "auto";
    // jsdom reports 0 for scrollHeight; leaving the height unset there keeps the class-based
    // minimum in charge instead of pinning the box to 0px.
    if (textarea.scrollHeight > 0) {
      textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeightPx)}px`;
    }
  }, [ref, value, maxHeightPx]);
}
