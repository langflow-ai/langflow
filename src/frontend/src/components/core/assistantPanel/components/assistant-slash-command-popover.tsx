import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/utils/utils";
import type { AssistantSlashCommand } from "../helpers/slash-commands";

interface AssistantSlashCommandPopoverProps {
  listboxId: string;
  items: AssistantSlashCommand[];
  activeIndex: number;
  onHover: (index: number) => void;
  onSelect: (index: number) => void;
}

export function slashCommandOptionId(listboxId: string, name: string): string {
  return `${listboxId}-${name}`;
}

export function AssistantSlashCommandPopover({
  listboxId,
  items,
  activeIndex,
  onHover,
  onSelect,
}: AssistantSlashCommandPopoverProps) {
  const { t } = useTranslation();
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  return (
    <div
      data-testid="assistant-slash-command-popover"
      className="absolute bottom-full left-2 z-40 mb-2 w-[70%] max-w-[calc(100%-1rem)] overflow-hidden rounded-md border border-border bg-background shadow-md"
    >
      <div
        id={listboxId}
        role="listbox"
        aria-label={t("assistant.slashCommands.label")}
        // Keep focus in the textarea: it owns the keyboard and aria-activedescendant.
        onMouseDown={(e) => e.preventDefault()}
        className="max-h-48 overflow-y-auto py-1"
      >
        {items.map((command, index) => (
          <button
            key={command.name}
            id={slashCommandOptionId(listboxId, command.name)}
            ref={index === activeIndex ? activeRef : undefined}
            type="button"
            role="option"
            tabIndex={-1}
            aria-selected={index === activeIndex}
            data-command={command.name}
            data-testid={`assistant-slash-command-option-${command.name}`}
            onMouseEnter={() => onHover(index)}
            onClick={() => onSelect(index)}
            className={cn(
              "flex w-full flex-col gap-0.5 px-3 py-1.5 text-left",
              index === activeIndex ? "bg-muted" : "hover:bg-muted/60",
            )}
          >
            <span className="flex items-baseline gap-2 font-mono text-sm">
              <span className="text-foreground">/{command.name}</span>
              {command.argumentHint && (
                <span className="text-xs text-muted-foreground">
                  {command.argumentHint}
                </span>
              )}
            </span>
            <span className="text-xs text-muted-foreground">
              {t(command.descriptionKey)}
            </span>
          </button>
        ))}
      </div>
      <div className="border-t border-border px-3 py-1 text-xs text-muted-foreground">
        {t("assistant.slashCommands.keyboardHint")}
      </div>
    </div>
  );
}
