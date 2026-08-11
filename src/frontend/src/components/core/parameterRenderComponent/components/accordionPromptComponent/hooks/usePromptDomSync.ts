import {
  type Dispatch,
  type MutableRefObject,
  type RefObject,
  type SetStateAction,
  useEffect,
} from "react";
import { getHighlightedHTML } from "../helpers/prompt-highlight";

/**
 * The three value↔DOM synchronization effects of the prompt editor,
 * moved verbatim from the component. The cursor-management cluster
 * intentionally stays in index.tsx (deferred follow-up); these effects
 * call it through the same function references passed in as props —
 * effect order and dependency arrays are identical to the originals.
 */
export function usePromptDomSync({
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
}: {
  value: string;
  internalValue: string;
  setInternalValue: Dispatch<SetStateAction<string>>;
  isOpen: boolean;
  isDoubleBrackets: boolean;
  contentEditableRef: RefObject<HTMLDivElement | null>;
  isTypingRef: MutableRefObject<boolean>;
  lastValidatedValueRef: MutableRefObject<string>;
  saveCursorPosition: () => void;
  restoreCursorPosition: () => void;
  resizeToFit: () => void;
}) {
  // Initialize content on mount and when value changes externally
  useEffect(() => {
    if (!isTypingRef.current && value !== internalValue) {
      setInternalValue(value);

      // Update DOM when value comes from external source
      if (contentEditableRef.current) {
        saveCursorPosition();
        contentEditableRef.current.innerHTML = value
          ? getHighlightedHTML(value, isDoubleBrackets)
          : "";
        restoreCursorPosition();
        resizeToFit();
      }

      // Update last validated value to avoid redundant calls
      lastValidatedValueRef.current = value;
    }
  }, [value]);

  // Update DOM when internal value changes (only on mount/external changes)
  useEffect(() => {
    if (!contentEditableRef.current || isTypingRef.current) return;

    const currentText = contentEditableRef.current.innerText;
    if (currentText !== internalValue) {
      contentEditableRef.current.innerHTML = internalValue
        ? getHighlightedHTML(internalValue, isDoubleBrackets)
        : "";
      resizeToFit();
    }
  }, [internalValue]);

  // Restore content when disclosure opens
  useEffect(() => {
    if (isOpen && contentEditableRef.current && internalValue) {
      // Small delay to ensure the DOM is ready after disclosure animation
      requestAnimationFrame(() => {
        if (contentEditableRef.current) {
          contentEditableRef.current.innerHTML = getHighlightedHTML(
            internalValue,
            isDoubleBrackets,
          );
          resizeToFit();
        }
      });
    }
  }, [isOpen]);
}
