import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { regexHighlight } from "@/constants/constants";
import { usePostValidatePrompt } from "@/controllers/API/queries/nodes/use-post-validate-prompt";
import MustachePromptModal from "@/modals/mustachePromptModal";
import PromptModal from "@/modals/promptModal";
import { cn } from "@/utils/utils";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputProps, PromptAreaComponentType } from "../../types";

/**
 * Generates a unique variable name for the prompt template.
 * If "variable_name" doesn't exist, returns it.
 * Otherwise, returns "variable_name_1", "variable_name_2", etc.
 */
export const generateUniqueVariableName = (
  templateValue: string,
  isDoubleBrackets: boolean = false,
): string => {
  // Match both single {var} and double {{var}} bracket patterns
  const variableRegex = isDoubleBrackets
    ? /\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g
    : /\{([^{}]+)\}/g;
  const existingVariables = new Set<string>();
  let match: RegExpExecArray | null;
  while ((match = variableRegex.exec(templateValue)) !== null) {
    existingVariables.add(match[1]);
  }

  let variableName = "variable_name";
  if (existingVariables.has(variableName)) {
    let counter = 1;
    while (existingVariables.has(`variable_name_${counter}`)) {
      counter++;
    }
    variableName = `variable_name_${counter}`;
  }

  return variableName;
};

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
  const [isOpen, setIsOpen] = useState(true);
  const [internalValue, setInternalValue] = useState(value);
  const [isScrollable, setIsScrollable] = useState(false);
  const contentEditableRef = useRef<HTMLDivElement>(null);
  const cursorPositionRef = useRef<number>(0);
  const isTypingRef = useRef(false);
  const { mutate: postValidatePrompt } = usePostValidatePrompt();
  const validateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastValidatedValueRef = useRef<string>(value);

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

  // Apply highlighting to the content
  const getHighlightedHTML = (text: string) => {
    if (isDoubleBrackets) {
      return text
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g, (match) => {
          return `<span class="chat-message-highlight">${match}</span>`;
        });
    }
    return text
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(
        regexHighlight,
        (match, codeFence, openRun, varName, closeRun) => {
          if (codeFence) return match;

          const lenOpen = openRun?.length ?? 0;
          const lenClose = closeRun?.length ?? 0;
          const isVariable = lenOpen === lenClose && lenOpen % 2 === 1;

          if (!isVariable) return match;

          const outerCount = Math.floor(lenOpen / 2);
          const outerLeft = "{".repeat(outerCount);
          const outerRight = "}".repeat(outerCount);

          return (
            `${outerLeft}` +
            `<span class="chat-message-highlight">{${varName}}</span>` +
            `${outerRight}`
          );
        },
      );
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

  // Initialize content on mount and when value changes externally
  useEffect(() => {
    if (!isTypingRef.current && value !== internalValue) {
      setInternalValue(value);

      // Update DOM when value comes from external source
      if (contentEditableRef.current) {
        saveCursorPosition();
        contentEditableRef.current.innerHTML = value
          ? getHighlightedHTML(value)
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
        ? getHighlightedHTML(internalValue)
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
          contentEditableRef.current.innerHTML =
            getHighlightedHTML(internalValue);
          resizeToFit();
        }
      });
    }
  }, [isOpen]);

  useEffect(() => {
    resizeToFit();
  }, []);

  // Validate prompt with debounce
  useEffect(() => {
    // Clear existing timeout
    if (validateTimeoutRef.current) {
      clearTimeout(validateTimeoutRef.current);
    }

    // Only validate if value has changed and is not empty
    if (
      internalValue &&
      internalValue !== "" &&
      internalValue !== lastValidatedValueRef.current &&
      nodeClass
    ) {
      validateTimeoutRef.current = setTimeout(() => {
        const valueToValidate = internalValue;
        postValidatePrompt(
          {
            name: field_name || "",
            template: valueToValidate,
            frontend_node: nodeClass,
            mustache: isDoubleBrackets,
          },
          {
            onSuccess: (apiReturn) => {
              if (
                apiReturn?.frontend_node &&
                valueToValidate === lastValidatedValueRef.current
              ) {
                lastValidatedValueRef.current = valueToValidate; // Redundant but safe
                apiReturn.frontend_node.template.template.value =
                  valueToValidate;
                if (handleNodeClass) {
                  handleNodeClass(apiReturn.frontend_node);
                }
              }
            },
            onError: (error) => {
              console.error("[AccordionPrompt] Validation error:", error);
            },
          },
        );
        lastValidatedValueRef.current = valueToValidate;
      }, 1000); // 1 second debounce
    }

    // Cleanup on unmount
    return () => {
      if (validateTimeoutRef.current) {
        clearTimeout(validateTimeoutRef.current);
      }
    };
  }, [internalValue, isDoubleBrackets, field_name]);

  // Track if this is the first render to avoid triggering on mount
  const isFirstRenderRef = useRef(true);

  // Force re-validation when isDoubleBrackets mode changes
  useEffect(() => {
    // Skip the first render (mount)
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }

    // Only trigger if we have a value and nodeClass
    if (internalValue && internalValue !== "" && nodeClass) {
      // Use queueMicrotask to defer validation until after current render cycle
      queueMicrotask(() => {
        // Reset the last validated value to force re-validation
        lastValidatedValueRef.current = "";

        postValidatePrompt(
          {
            name: field_name || "",
            template: internalValue,
            frontend_node: nodeClass,
            mustache: isDoubleBrackets,
          },
          {
            onSuccess: (apiReturn) => {
              if (apiReturn?.frontend_node) {
                lastValidatedValueRef.current = internalValue;
                apiReturn.frontend_node.template.template.value = internalValue;
                if (handleNodeClass) {
                  // Merge the updated template fields while preserving existing properties
                  const updatedNode = {
                    ...nodeClass,
                    template: {
                      ...nodeClass.template,
                      ...apiReturn.frontend_node.template,
                    },
                  };
                  handleNodeClass(updatedNode);
                }
              }
            },
            onError: (error) => {
              console.error(
                "[AccordionPrompt] Mode change validation error:",
                error,
              );
            },
          },
        );
      });
    }
  }, [isDoubleBrackets]);

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
      ? getHighlightedHTML(normalizedValue)
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
    contentEditableRef.current.innerHTML = getHighlightedHTML(newValue);
    resizeToFit();
  };

  const handlePromptModalSetValue = (newValue: string) => {
    lastValidatedValueRef.current = newValue;
    setInternalValue(newValue);
    handleOnNewValue({ value: newValue });
    if (contentEditableRef.current) {
      contentEditableRef.current.innerHTML = getHighlightedHTML(newValue);
    }
  };

  const ModalComponent = isDoubleBrackets ? MustachePromptModal : PromptModal;

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
            title="Add variable"
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
          <div className="relative">
            <div
              ref={contentEditableRef}
              contentEditable={!disabled && !readonly}
              onInput={handleInput}
              onKeyDown={handleKeyDown}
              suppressContentEditableWarning
              id={id}
              data-testid={id}
              className={cn(
                "relative min-h-10 overflow-y-auto rounded-md border bg-background px-3 py-2 pr-8 text-sm outline-none break-words whitespace-pre-wrap",
                "focus:border-primary hover:border-muted-foreground",
                "before:content-[''] before:pointer-events-none before:absolute before:left-3 before:top-2 before:text-muted-foreground",
                "empty:before:content-[attr(data-placeholder)]",
                disabled && "cursor-not-allowed opacity-50",
                readonly && "cursor-default",
                !internalValue && "text-muted-foreground",
              )}
              data-placeholder={getPlaceholder(
                disabled,
                "Type your prompt here...",
              )}
            />
            {!disabled && (
              <div
                className={cn(
                  "absolute top-1 z-10 flex items-center gap-1",
                  isScrollable ? "right-3" : "right-1",
                )}
              >
                <ModalComponent
                  id={id}
                  field_name={field_name}
                  readonly={readonly}
                  value={value}
                  setValue={handlePromptModalSetValue}
                  nodeClass={nodeClass}
                  setNodeClass={handleNodeClass}
                >
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0 text-muted-foreground"
                    title="Fullscreen"
                    data-testid={
                      isDoubleBrackets
                        ? "button_open_mustache_prompt_modal"
                        : "button_open_prompt_modal"
                    }
                  >
                    <ForwardedIconComponent
                      name="Maximize"
                      className="h-3.5 w-3.5"
                    />
                  </Button>
                </ModalComponent>
              </div>
            )}
          </div>
        </DisclosureContent>
      </Disclosure>
    </div>
  );
}
