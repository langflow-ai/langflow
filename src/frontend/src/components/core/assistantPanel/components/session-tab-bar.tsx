import { useCallback, useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import {
  ASSISTANT_SESSION_PREVIEW_LENGTH,
  ASSISTANT_TAB_SCROLL_AMOUNT,
} from "../assistant-panel.constants";
import type { SessionHistoryEntry } from "../assistant-panel.types";

interface SessionTabBarProps {
  sessions: SessionHistoryEntry[];
  activeSessionId: string;
  hasMessages: boolean;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onNewSession: () => void;
}

interface TabItem {
  id: string;
  label: string;
  isCurrent: boolean;
}

export function SessionTabBar({
  sessions,
  activeSessionId,
  hasMessages,
  onSelectSession,
  onDeleteSession,
  onNewSession,
}: SessionTabBarProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeTabRef = useRef<HTMLButtonElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Build tab list: saved sessions in order, plus current live session at the end
  // Like Chrome: tabs stay in their position, active one is just highlighted
  const tabs: TabItem[] = [];
  const isLiveSessionSaved = sessions.some(
    (s) => s.sessionId === activeSessionId,
  );

  // Saved sessions in their stored order
  for (const session of sessions) {
    tabs.push({
      id: session.sessionId,
      label:
        session.firstUserMessage.slice(0, ASSISTANT_SESSION_PREVIEW_LENGTH) ||
        "Empty session",
      isCurrent: session.sessionId === activeSessionId,
    });
  }

  // If the active session isn't saved yet, add it at the end (like a new Chrome tab)
  if (!isLiveSessionSaved) {
    tabs.push({
      id: activeSessionId,
      label: hasMessages ? "Current session" : "New session",
      isCurrent: true,
    });
  }

  const checkOverflow = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 2);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    checkOverflow();

    const observer = new ResizeObserver(checkOverflow);
    observer.observe(el);
    el.addEventListener("scroll", checkOverflow, { passive: true });

    return () => {
      observer.disconnect();
      el.removeEventListener("scroll", checkOverflow);
    };
  }, [checkOverflow, tabs.length]);

  // Scroll active tab fully into view when it changes or tabs change
  useEffect(() => {
    // Small delay to let the DOM update after tab list changes
    const timer = setTimeout(() => {
      const tab = activeTabRef.current;
      const container = scrollRef.current;
      if (!tab || !container) return;

      const tabLeft = tab.offsetLeft;
      const tabRight = tabLeft + tab.offsetWidth;
      const viewLeft = container.scrollLeft;
      const viewRight = viewLeft + container.clientWidth;

      if (tabLeft < viewLeft) {
        container.scrollTo({ left: tabLeft - 4, behavior: "smooth" });
      } else if (tabRight > viewRight) {
        container.scrollTo({
          left: tabRight - container.clientWidth + 4,
          behavior: "smooth",
        });
      }
      // Re-check overflow after scroll
      checkOverflow();
    }, 50);
    return () => clearTimeout(timer);
  }, [activeSessionId, tabs.length, checkOverflow]);

  const scrollBy = (amount: number) => {
    scrollRef.current?.scrollBy({ left: amount, behavior: "smooth" });
  };

  return (
    <div
      className="relative flex min-w-0 flex-1 items-center"
      data-testid="session-tab-bar"
    >
      {/* Left scroll arrow — absolute overlay */}
      {canScrollLeft && (
        <button
          type="button"
          data-testid="tab-scroll-left"
          className="absolute left-0 top-0 z-10 flex h-full w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
          onClick={() => scrollBy(-ASSISTANT_TAB_SCROLL_AMOUNT)}
        >
          <ForwardedIconComponent name="ChevronLeft" className="h-4 w-4" />
        </button>
      )}

      {/* Scrollable tab strip */}
      <div
        ref={scrollRef}
        className="flex items-end overflow-x-auto"
        style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
      >
        {tabs.map((tab) => {
          const isActive = tab.id === activeSessionId;
          return (
            <button
              key={tab.id}
              ref={isActive ? activeTabRef : undefined}
              type="button"
              data-testid={`session-tab-${tab.id}`}
              onClick={() => {
                if (!isActive) onSelectSession(tab.id);
              }}
              className={cn(
                "group relative flex shrink-0 items-center gap-1.5 px-3 py-1.5 text-xs transition-colors",
                "w-[7.5rem] rounded-t-md border border-b-0",
                isActive
                  ? "border-border bg-background text-foreground font-medium"
                  : "border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground",
              )}
            >
              <span className="truncate">{tab.label}</span>

              {/* Close button — hide only when it's the last remaining tab */}
              {tabs.length > 1 && (
                <span
                  role="button"
                  tabIndex={0}
                  data-testid={`session-tab-close-${tab.id}`}
                  className="ml-auto shrink-0 rounded-sm p-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:text-foreground"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (isActive) {
                      // Closing the active tab — switch to another first
                      const otherTab = tabs.find((t) => t.id !== tab.id);
                      if (otherTab) {
                        onSelectSession(otherTab.id);
                      } else {
                        onNewSession();
                      }
                    }
                    onDeleteSession(tab.id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.stopPropagation();
                      if (isActive) {
                        const otherTab = tabs.find((t) => t.id !== tab.id);
                        if (otherTab) {
                          onSelectSession(otherTab.id);
                        } else {
                          onNewSession();
                        }
                      }
                      onDeleteSession(tab.id);
                    }
                  }}
                >
                  <ForwardedIconComponent name="X" className="h-3 w-3" />
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Right scroll arrow — absolute overlay */}
      {canScrollRight && (
        <button
          type="button"
          data-testid="tab-scroll-right"
          className="absolute right-0 top-0 z-10 flex h-full w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
          onClick={() => scrollBy(ASSISTANT_TAB_SCROLL_AMOUNT)}
        >
          <ForwardedIconComponent name="ChevronRight" className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
