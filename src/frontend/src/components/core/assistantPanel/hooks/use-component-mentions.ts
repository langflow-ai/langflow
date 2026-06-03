import { type RefObject, useCallback, useRef, useState } from "react";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType, GenericNodeType } from "@/types/flow";
import {
  detectMention,
  formatMentionToken,
  replaceMention,
} from "../helpers/mention-parsing";

export interface MentionItem {
  id: string;
  displayName: string;
  type: string;
  icon?: string;
}

interface UseComponentMentionsParams {
  value: string;
  setValue: (value: string) => void;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
}

export interface UseComponentMentionsReturn {
  isOpen: boolean;
  items: MentionItem[];
  activeIndex: number;
  /** Re-evaluate the ``@`` trigger after the value or caret changed. */
  handleValueChange: (value: string, caret: number) => void;
  /** Handle navigation keys while the popover is open. Returns ``true`` when
   * the key was consumed so the caller skips its own handler (send, history). */
  handleKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => boolean;
  /** Move the highlight to ``index`` (hover) and preview that node on canvas. */
  setActiveIndex: (index: number) => void;
  /** Commit the mention at ``index`` (or the active one) into the input. */
  confirm: (index?: number) => void;
  close: () => void;
}

const isGeneric = (node: AllNodeType): node is GenericNodeType =>
  node.type === "genericNode";

function toItem(node: GenericNodeType): MentionItem {
  return {
    id: node.data.id ?? node.id,
    displayName: node.data.node?.display_name ?? node.data.type,
    type: node.data.type,
    icon: node.data.node?.icon,
  };
}

function filterItems(items: MentionItem[], query: string): MentionItem[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter(
    (item) =>
      item.displayName.toLowerCase().includes(q) ||
      item.id.toLowerCase().includes(q) ||
      item.type.toLowerCase().includes(q),
  );
}

export function useComponentMentions({
  value,
  setValue,
  textareaRef,
}: UseComponentMentionsParams): UseComponentMentionsReturn {
  const [isOpen, setIsOpen] = useState(false);
  const [items, setItems] = useState<MentionItem[]>([]);
  const [activeIndex, setActiveIndexState] = useState(0);
  const mentionStartRef = useRef(0);
  // Canvas selection captured when the popover opened, restored on cancel so
  // typing ``@`` never permanently changes the user's prior selection.
  const priorSelectionRef = useRef<Set<string> | null>(null);

  const highlightNode = useCallback((id: string) => {
    useFlowStore.getState().setNodes((nodes) =>
      nodes.map((node) => {
        const selected = node.id === id;
        return node.selected === selected ? node : { ...node, selected };
      }),
    );
  }, []);

  const restoreSelection = useCallback(() => {
    const prior = priorSelectionRef.current;
    if (!prior) return;
    useFlowStore.getState().setNodes((nodes) =>
      nodes.map((node) => {
        const selected = prior.has(node.id);
        return node.selected === selected ? node : { ...node, selected };
      }),
    );
  }, []);

  const reset = useCallback(() => {
    setIsOpen(false);
    setItems([]);
    setActiveIndexState(0);
    priorSelectionRef.current = null;
  }, []);

  const close = useCallback(() => {
    restoreSelection();
    reset();
  }, [restoreSelection, reset]);

  const setActiveIndex = useCallback(
    (index: number) => {
      setActiveIndexState(index);
      const item = items[index];
      if (item) highlightNode(item.id);
    },
    [items, highlightNode],
  );

  const handleValueChange = useCallback(
    (nextValue: string, caret: number) => {
      const match = detectMention(nextValue, caret);
      if (!match) {
        if (isOpen) close();
        return;
      }

      const all = useFlowStore.getState().nodes.filter(isGeneric).map(toItem);
      const filtered = filterItems(all, match.query);
      mentionStartRef.current = match.start;

      if (!isOpen) {
        priorSelectionRef.current = new Set(
          useFlowStore
            .getState()
            .nodes.filter((node) => node.selected)
            .map((node) => node.id),
        );
        setIsOpen(true);
      }

      setItems(filtered);
      setActiveIndexState(0);
      if (filtered[0]) highlightNode(filtered[0].id);
    },
    [isOpen, close, highlightNode],
  );

  const confirm = useCallback(
    (index?: number) => {
      const item = items[index ?? activeIndex];
      if (!item) {
        close();
        return;
      }
      const textarea = textareaRef.current;
      const caret = textarea ? textarea.selectionStart : value.length;
      const { value: nextValue, caret: nextCaret } = replaceMention(
        value,
        mentionStartRef.current,
        caret,
        formatMentionToken(item.id),
      );
      setValue(nextValue);
      // Leave the confirmed node selected on the canvas (it already is from the
      // preview highlight) — the mention is committed, so don't restore.
      reset();
      requestAnimationFrame(() => {
        const target = textareaRef.current;
        if (target) {
          target.focus();
          target.setSelectionRange(nextCaret, nextCaret);
        }
      });
    },
    [items, activeIndex, value, setValue, textareaRef, reset, close],
  );

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>): boolean => {
      if (!isOpen) return false;
      const count = items.length;
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          if (count) setActiveIndex((activeIndex + 1) % count);
          return true;
        case "ArrowUp":
          event.preventDefault();
          if (count) setActiveIndex((activeIndex - 1 + count) % count);
          return true;
        case "Tab":
          event.preventDefault();
          if (count) {
            const step = event.shiftKey ? -1 : 1;
            setActiveIndex((activeIndex + step + count) % count);
          }
          return true;
        case "Enter":
          event.preventDefault();
          if (count) confirm();
          else close();
          return true;
        case "Escape":
          event.preventDefault();
          close();
          return true;
        default:
          return false;
      }
    },
    [isOpen, items.length, activeIndex, setActiveIndex, confirm, close],
  );

  return {
    isOpen,
    items,
    activeIndex,
    handleValueChange,
    handleKeyDown,
    setActiveIndex,
    confirm,
    close,
  };
}
