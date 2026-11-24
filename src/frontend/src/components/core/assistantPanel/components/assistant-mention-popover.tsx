import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";
import type { MentionItem } from "../hooks/use-component-mentions";

interface AssistantMentionPopoverProps {
  items: MentionItem[];
  activeIndex: number;
  onHover: (index: number) => void;
  onSelect: (index: number) => void;
}

export function AssistantMentionPopover({
  items,
  activeIndex,
  onHover,
  onSelect,
}: AssistantMentionPopoverProps) {
  const { t } = useTranslation();
  const activeRef = useRef<HTMLButtonElement>(null);

  // Keep the keyboard-highlighted option in view as the user arrows through a
  // list taller than the popover.
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  return (
    <div
      data-testid="assistant-mention-popover"
      role="listbox"
      // Keep the textarea focused when clicking an item so the caret position
      // used for token insertion stays valid.
      onMouseDown={(e) => e.preventDefault()}
      className="absolute bottom-full left-2 z-40 mb-2 max-h-48 w-[70%] max-w-[calc(100%-1rem)] overflow-y-auto rounded-md border border-border bg-background py-1 shadow-md"
    >
      {items.length === 0 ? (
        <div className="px-3 py-2 text-xs text-muted-foreground">
          {t("assistant.mentionNoMatches")}
        </div>
      ) : (
        items.map((item, index) => (
          <button
            key={item.id}
            ref={index === activeIndex ? activeRef : undefined}
            type="button"
            role="option"
            aria-selected={index === activeIndex}
            data-testid={`assistant-mention-option-${item.id}`}
            onMouseEnter={() => onHover(index)}
            onClick={() => onSelect(index)}
            className={cn(
              "flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm",
              index === activeIndex
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted/60",
            )}
          >
            {item.kind === "field" ? (
              <span className="truncate text-foreground">
                {item.displayName}
              </span>
            ) : (
              <>
                <ForwardedIconComponent
                  name={item.icon || "ToyBrick"}
                  className="h-4 w-4 shrink-0"
                />
                <span className="truncate text-foreground">
                  {item.displayName}
                </span>
                <span className="truncate text-xs text-muted-foreground">
                  {item.type}
                </span>
              </>
            )}
          </button>
        ))
      )}
    </div>
  );
}
