import { useEffect, useRef } from "react";
import { useStickToBottomContext } from "use-stick-to-bottom";

export const isSafari =
  typeof navigator !== "undefined" &&
  /safari/i.test(navigator.userAgent) &&
  !/chrome|chromium|android/i.test(navigator.userAgent);

/** Minimum pixels to detect intentional touch scroll */
const TOUCH_SCROLL_THRESHOLD = 10;
/** Cooldown (ms) to prevent immediate re-engage during momentum scroll */
const SCROLL_RE_ENGAGE_COOLDOWN_MS = 800;
/** Pixels from bottom to trigger stick-to-bottom re-engage */
const BOTTOM_PROXIMITY_THRESHOLD = 20;
/** Maximum scroll delta considered natural (blocks sudden jumps) */
const JITTER_THRESHOLD = 200;

/**
 * Safari-specific workaround for scroll jitter when using stick-to-bottom behavior.
 *
 * Safari exhibits scroll position jumps when content height changes dynamically.
 * This component uses a RAF loop to enforce scroll position and detect/block
 * unnatural scroll jumps while preserving user scroll intent.
 */
export function SafariScrollFix() {
  if (!isSafari) return null;
  return <SafariScrollFixInner />;
}

function SafariScrollFixInner() {
  const { scrollRef, stopScroll } = useStickToBottomContext();
  const stickyRef = useRef(true);
  const lastKnownScrollTop = useRef(0);
  const touchStartYRef = useRef(0);

  useEffect(() => {
    const scrollEl = scrollRef.current;
    if (!scrollEl) return;

    lastKnownScrollTop.current = scrollEl.scrollTop;
    let disengageTime = 0;

    // Detect user scrolling UP via wheel
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY < 0) {
        if (stickyRef.current) {
          stickyRef.current = false;
          lastKnownScrollTop.current = scrollEl.scrollTop;
        }
        // Reset cooldown on every scroll-up wheel event (trackpad momentum)
        disengageTime = Date.now();
      }
    };

    // Detect user scrolling UP via touch (finger moves down = content scrolls up)
    const onTouchStart = (e: TouchEvent) => {
      touchStartYRef.current = e.touches[0].clientY;
    };
    const onTouchMove = (e: TouchEvent) => {
      if (
        e.touches[0].clientY >
        touchStartYRef.current + TOUCH_SCROLL_THRESHOLD
      ) {
        if (stickyRef.current) {
          stickyRef.current = false;
          lastKnownScrollTop.current = scrollEl.scrollTop;
        }
        disengageTime = Date.now();
      }
    };

    // Re-engage when user scrolls back to near the bottom
    // (but not during the cooldown period after user scrolled up)
    const onScroll = () => {
      if (
        !stickyRef.current &&
        Date.now() - disengageTime > SCROLL_RE_ENGAGE_COOLDOWN_MS
      ) {
        const { scrollTop, scrollHeight, clientHeight } = scrollEl;
        if (
          scrollHeight - scrollTop - clientHeight <
          BOTTOM_PROXIMITY_THRESHOLD
        ) {
          stickyRef.current = true;
        }
      }
    };

    scrollEl.addEventListener("wheel", onWheel, { passive: true });
    scrollEl.addEventListener("touchstart", onTouchStart, { passive: true });
    scrollEl.addEventListener("touchmove", onTouchMove, { passive: true });
    scrollEl.addEventListener("scroll", onScroll, { passive: true });

    let rafId: ReturnType<typeof requestAnimationFrame>;
    const tick = () => {
      if (stickyRef.current && scrollEl) {
        // Sticky mode: suppress library, force to bottom
        stopScroll();
        scrollEl.scrollTop = scrollEl.scrollHeight;
        lastKnownScrollTop.current = scrollEl.scrollTop;
      } else if (scrollEl) {
        // User scrolled up: jitter guard — allow gradual changes, block jumps
        const currentTop = scrollEl.scrollTop;
        const delta = Math.abs(currentTop - lastKnownScrollTop.current);

        if (delta > JITTER_THRESHOLD) {
          // Unnatural jump detected — restore last known good position
          scrollEl.scrollTop = lastKnownScrollTop.current;
        } else {
          // Normal gradual scroll — update last known position
          lastKnownScrollTop.current = currentTop;
        }
      }
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);

    return () => {
      scrollEl.removeEventListener("wheel", onWheel);
      scrollEl.removeEventListener("touchstart", onTouchStart);
      scrollEl.removeEventListener("touchmove", onTouchMove);
      scrollEl.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(rafId);
    };
  }, [scrollRef, stopScroll]);

  return null;
}
