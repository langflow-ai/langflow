import { useEffect, useRef } from "react";
import { useStickToBottomContext } from "use-stick-to-bottom";

export const isSafari =
  typeof navigator !== "undefined" &&
  /safari/i.test(navigator.userAgent) &&
  !/chrome|chromium|android/i.test(navigator.userAgent);

/**
 * Hacky Safari fix: rAF loop that takes over scroll control.
 * When sticky (at bottom): forces scrollTop = scrollHeight every frame.
 * When user scrolled up: uses a jitter guard that allows gradual user
 * scrolling but blocks sudden jumps (caused by the library or Safari).
 */
export function SafariScrollFix() {
  const { scrollRef, stopScroll } = useStickToBottomContext();
  const stickyRef = useRef(true);
  const stopScrollRef = useRef(stopScroll);
  stopScrollRef.current = stopScroll;
  const lastKnownScrollTop = useRef(0);

  useEffect(() => {
    if (!isSafari) return;

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
    let touchStartY = 0;
    const onTouchStart = (e: TouchEvent) => {
      touchStartY = e.touches[0].clientY;
    };
    const onTouchMove = (e: TouchEvent) => {
      if (e.touches[0].clientY > touchStartY + 10) {
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
      if (!stickyRef.current && Date.now() - disengageTime > 800) {
        const { scrollTop, scrollHeight, clientHeight } = scrollEl;
        if (scrollHeight - scrollTop - clientHeight < 20) {
          stickyRef.current = true;
        }
      }
    };

    scrollEl.addEventListener("wheel", onWheel, { passive: true });
    scrollEl.addEventListener("touchstart", onTouchStart, { passive: true });
    scrollEl.addEventListener("touchmove", onTouchMove, { passive: true });
    scrollEl.addEventListener("scroll", onScroll, { passive: true });

    let rafId: number;
    const tick = () => {
      if (stickyRef.current && scrollEl) {
        // Sticky mode: suppress library, force to bottom
        stopScrollRef.current();
        scrollEl.scrollTop = scrollEl.scrollHeight;
        lastKnownScrollTop.current = scrollEl.scrollTop;
      } else if (scrollEl) {
        // User scrolled up: jitter guard — allow gradual changes, block jumps
        const currentTop = scrollEl.scrollTop;
        const delta = Math.abs(currentTop - lastKnownScrollTop.current);

        if (delta > 200) {
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
  }, [scrollRef]);

  return null;
}
