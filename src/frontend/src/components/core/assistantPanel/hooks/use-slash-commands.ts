import { useCallback, useState } from "react";
import {
  type AssistantSlashCommand,
  detectSlashCommandQuery,
  filterSlashCommands,
} from "../helpers/slash-commands";

interface UseSlashCommandsParams {
  /** Write the picked command into the draft; the user sends it with a second Enter. */
  onComplete: (text: string) => void;
}

export interface UseSlashCommandsReturn {
  isOpen: boolean;
  items: AssistantSlashCommand[];
  activeIndex: number;
  handleValueChange: (value: string, caret: number) => void;
  /** Returns true when the key was consumed, so the input skips send/history handling. */
  handleKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => boolean;
  setActiveIndex: (index: number) => void;
  complete: (index?: number) => void;
  close: () => void;
}

export function useSlashCommands({
  onComplete,
}: UseSlashCommandsParams): UseSlashCommandsReturn {
  const [items, setItems] = useState<AssistantSlashCommand[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const isOpen = items.length > 0;

  const close = useCallback(() => {
    setItems([]);
    setActiveIndex(0);
  }, []);

  const handleValueChange = useCallback((value: string, caret: number) => {
    const query = detectSlashCommandQuery(value, caret);
    const matches = query === null ? [] : filterSlashCommands(query);
    setItems(matches);
    setActiveIndex((current) =>
      current < matches.length ? current : Math.max(0, matches.length - 1),
    );
  }, []);

  const complete = useCallback(
    (index?: number) => {
      const command = items[index ?? activeIndex];
      if (!command) return;
      close();
      onComplete(`/${command.name}${command.argumentHint ? " " : ""}`);
    },
    [items, activeIndex, close, onComplete],
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>): boolean => {
      if (!isOpen) return false;
      const count = items.length;
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setActiveIndex((activeIndex + 1) % count);
          return true;
        case "ArrowUp":
          event.preventDefault();
          setActiveIndex((activeIndex - 1 + count) % count);
          return true;
        case "Tab":
        case "Enter":
          if (event.shiftKey) return false;
          event.preventDefault();
          complete();
          return true;
        case "Escape":
          event.preventDefault();
          // The flow page closes the whole Assistant on Escape; dismiss only the menu.
          event.stopPropagation();
          close();
          return true;
        default:
          return false;
      }
    },
    [isOpen, items.length, activeIndex, complete, close],
  );

  return {
    isOpen,
    items,
    activeIndex,
    handleValueChange,
    handleKeyDown,
    setActiveIndex,
    complete,
    close,
  };
}
