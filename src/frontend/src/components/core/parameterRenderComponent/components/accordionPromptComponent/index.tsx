import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { cn } from "@/utils/utils";
import type { InputProps, PromptAreaComponentType } from "../../types";
import { PromptEditableArea } from "./components/PromptEditableArea";
import { generateUniqueVariableName } from "./helpers/generate-unique-variable-name";
import { getHighlightedHTML } from "./helpers/prompt-highlight";
import { usePromptDomSync } from "./hooks/usePromptDomSync";
import { usePromptValidation } from "./hooks/usePromptValidation";

/** @deprecated import from "./helpers/generate-unique-variable-name" */
export { generateUniqueVariableName } from "./helpers/generate-unique-variable-name";

export default function AccordionPromptComponent({
  field_name,
  nodeClass,
  handleOnNewValue,
  handleNodeClass,
  value,
  disabled,
  id = "",
  readonly = false,
  showParameter = false,
  isDoubleBrackets = false,
}: InputProps<string, PromptAreaComponentType>): JSX.Element {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(true);
  const [internalValue, setInternalValue] = useState(value);
  const [isScrollable, setIsScrollable] = useState(false);
  const contentEditableRef = useRef<HTMLDivElement>(null);
  const cursorPositionRef = useRef<number>(0);
  const isTypingRef = useRef(false);
  const { lastValidatedValueRef } = usePromptValidation({
    value,
    internalValue,
    isDoubleBrackets,
    field_name,
    nodeClass,
    handleNodeClass,
  });

  const resizeToFit = () => {
    const el = contentEditableRef.current;
    if (!el) return;

    const baseHeightPx = 40;
    const multilineMinHeightPx = 60;
    const maxHeightPx = 96;

    el.style.height = "auto";
    const scrollHeight = el.scrollHeight;
    const minHeight =
      scrollHeight > baseHeightPx ? multilineMinHeightPx : baseHeightPx;
    const nextHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeightPx);

    el.style.height = `${nextHeight}px`;
    el.style.overflowY = scrollHeight > maxHeightPx ? "auto" : "hidden";
    setIsScrollable(scrollHeight > nextHeight);
  };

  const getCursorOffset = () => {
    const selection = window.getSelection();
    if (!selection || !contentEditableRef.current || selection.rangeCount === 0)
      return null;

    const range = selection.getRangeAt(0);
    if (!contentEditableRef.current.contains(range.commonAncestorContainer))
      return null;

    const marker = document.createTextNode("\uFEFF");
    range.insertNode(marker);
    const text = contentEditableRef.current.innerText;
    const index = text.indexOf("\uFEFF");
    marker.parentNode?.removeChild(marker);

    return index !== -1 ? index : null;
  };

  // Save cursor position - count actual characters including newlines
  const saveCursorPosition = () => {
    const offset = getCursorOffset();
    if (offset !== null) {
      cursorPositionRef.current = offset;
    }
  };

  // Scroll the cursor into view
  const scrollToCursor = () => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || !contentEditableRef.current)
      return;

    const range = selection.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const containerRect = contentEditableRef.current.getBoundingClientRect();

    // Check if cursor is below the visible area
    if (rect.bottom > containerRect.bottom) {
      contentEditableRef.current.scrollTop +=
        rect.bottom - containerRect.bottom + 10;
    }
    // Check if cursor is above the visible area
    else if (rect.top < containerRect.top) {
      contentEditableRef.current.scrollTop -= containerRect.top - rect.top + 10;
    }

    // Update scrollable state
    const hasScroll =
      contentEditableRef.current.scrollHeight >
      contentEditableRef.current.clientHeight;
    setIsScrollable(hasScroll);
  };

  // Restore cursor position
  const restoreCursorPosition = () => {
    if (!contentEditableRef.current) return;

    const selection = window.getSelection();
    if (!selection) return;

    const targetOffset = cursorPositionRef.current;
    let currentOffset = 0;

    // Function to set cursor at a specific position
    const setCursorAt = (node: Node, offset: number) => {
      try {
        const newRange = document.createRange();
        newRange.setStart(node, offset);
        newRange.collapse(true);
        selection.removeAllRanges();
        selection.addRange(newRange);
      } catch (e) {
        if (e instanceof DOMException && e.name === "IndexSizeError") {
          // Ignore range errors
          return;
        }
        console.error(
          "An unexpected error occurred while setting the cursor position:",
          e,
        );
      }
    };

    // Recursive function to find the right position
    const findPosition = (node: Node): boolean => {
      if (node.nodeType === Node.TEXT_NODE) {
        const nodeLength = node.textContent?.length || 0;

        if (currentOffset + nodeLength >= targetOffset) {
          const offset = targetOffset - currentOffset;
          setCursorAt(node, Math.min(offset, nodeLength));
          return true;
        }

        currentOffset += nodeLength;
      } else if (node.nodeName === "BR") {
        // BR represents a newline character
        currentOffset += 1;

        if (currentOffset >= targetOffset) {
          // Cursor should be right after the BR
          const parent = node.parentNode;
          if (parent) {
            const nextSibling = node.nextSibling;
            if (nextSibling) {
              if (nextSibling.nodeType === Node.TEXT_NODE) {
                setCursorAt(nextSibling, 0);
              } else {
                setCursorAt(
                  parent,
                  Array.from(parent.childNodes).indexOf(node as ChildNode) + 1,
                );
              }
            } else {
              // BR is the last child, place cursor at end of parent
              setCursorAt(parent, parent.childNodes.length);
            }
          }
          return true;
        }
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        // Recursively process child nodes
        for (const child of Array.from(node.childNodes)) {
          if (findPosition(child)) {
            return true;
          }
        }
      }

      return false;
    };

    findPosition(contentEditableRef.current);
  };

  // Value <-> DOM synchronization effects
  usePromptDomSync({
    value,
    internalValue,
    setInternalValue,
    isOpen,
    isDoubleBrackets,
    contentEditableRef,
    isTypingRef,
    lastValidatedValueRef,
    saveCursorPosition,
    restoreCursorPosition,
    resizeToFit,
  });

  useEffect(() => {
    resizeToFit();
  }, []);

  const handleInput = (e: React.FormEvent<HTMLDivElement>) => {
    if (!contentEditableRef.current) return;

    const rawValue = contentEditableRef.current.innerText;
    const newValue = rawValue.replace(/\u200B/g, "");
    const normalizedValue = newValue.trim() === "" ? "" : newValue;

    if (normalizedValue === internalValue) return;

    isTypingRef.current = true;

    // Update internal state
    setInternalValue(normalizedValue);

    // Notify parent immediately
    handleOnNewValue({ value: normalizedValue });

    // Check if we need to update HTML for highlighting
    const currentHTML = contentEditableRef.current.innerHTML;
    const expectedHTML = normalizedValue
      ? getHighlightedHTML(normalizedValue, isDoubleBrackets)
      : "";

    // Only update if the HTML actually needs to change (for highlighting)
    // This prevents unnecessary updates that mess with cursor position
    if (currentHTML !== expectedHTML) {
      // Save cursor position
      saveCursorPosition();

      // Update the highlighted HTML
      contentEditableRef.current.innerHTML = expectedHTML;

      // Restore cursor position
      restoreCursorPosition();
    }

    if (normalizedValue === "") {
      contentEditableRef.current.innerHTML = "";
    }

    // Reset typing flag after current event loop completes
    queueMicrotask(() => {
      isTypingRef.current = false;
    });

    // Scroll cursor into view
    scrollToCursor();

    resizeToFit();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();

      if (!contentEditableRef.current) return;

      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0) return;

      const range = selection.getRangeAt(0);
      range.deleteContents();

      // Insert a BR element for the line break
      const br = document.createElement("br");
      range.insertNode(br);

      // Create an empty text node after the BR for cursor positioning
      const textNode = document.createTextNode("\u200B"); // Zero-width space
      br.after(textNode);

      // Move cursor after the zero-width space
      range.setStartAfter(textNode);
      range.setEndAfter(textNode);

      selection.removeAllRanges();
      selection.addRange(range);

      // Trigger input event logic manually
      const event = new Event("input", { bubbles: true });
      contentEditableRef.current.dispatchEvent(event);

      // Scroll cursor into view
      scrollToCursor();
      resizeToFit();
    }
  };

  const handleAddVariable = () => {
    if (disabled || readonly || !contentEditableRef.current) return;

    isTypingRef.current = true;

    const variableName = generateUniqueVariableName(
      internalValue,
      isDoubleBrackets,
    );
    const variableText = isDoubleBrackets
      ? `{{${variableName}}}`
      : `{${variableName}}`;

    // Get current cursor position or end of text
    let insertPosition = internalValue.length;
    const currentCursor = getCursorOffset();
    if (currentCursor !== null) {
      insertPosition = currentCursor;
    }

    // Insert variable into text
    const newValue =
      internalValue.substring(0, insertPosition) +
      variableText +
      internalValue.substring(insertPosition);

    setInternalValue(newValue);
    handleOnNewValue({ value: newValue });

    // Update DOM with highlighting
    contentEditableRef.current.innerHTML = getHighlightedHTML(
      newValue,
      isDoubleBrackets,
    );
    resizeToFit();
  };

  const handlePromptModalSetValue = (newValue: string) => {
    lastValidatedValueRef.current = newValue;
    setInternalValue(newValue);
    handleOnNewValue({ value: newValue });
    if (contentEditableRef.current) {
      contentEditableRef.current.innerHTML = getHighlightedHTML(
        newValue,
        isDoubleBrackets,
      );
    }
  };

  if (!showParameter) return <></>;

  return (
    <div className={cn("relative w-full", disabled && "pointer-events-none")}>
      <Disclosure open={isOpen} onOpenChange={setIsOpen}>
        <div className="absolute right-0 -top-8 z-10 flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleAddVariable}
            disabled={disabled || readonly}
            className="h-6 w-6 p-0 text-muted-foreground"
            title={t("accordion.addVariable")}
          >
            <span className="text-xs">
              {isDoubleBrackets ? "{{+}}" : "{+}"}
            </span>
          </Button>
          <DisclosureTrigger className="group/collapsible">
            <div
              role="button"
              tabIndex={0}
              className="flex h-4 w-4 cursor-pointer items-center justify-center"
            >
              <ForwardedIconComponent
                name="ChevronRight"
                className={cn(
                  "h-4 w-4 text-muted-foreground transition-transform duration-200",
                  isOpen && "rotate-90",
                )}
              />
            </div>
          </DisclosureTrigger>
        </div>

        <DisclosureContent>
          <PromptEditableArea
            contentEditableRef={contentEditableRef}
            disabled={disabled}
            readonly={readonly}
            id={id}
            internalValue={internalValue}
            isScrollable={isScrollable}
            isDoubleBrackets={isDoubleBrackets}
            field_name={field_name}
            value={value}
            nodeClass={nodeClass}
            handleNodeClass={handleNodeClass}
            onInput={handleInput}
            onKeyDown={handleKeyDown}
            onPromptModalSetValue={handlePromptModalSetValue}
          />
        </DisclosureContent>
      </Disclosure>
    </div>
  );
}
