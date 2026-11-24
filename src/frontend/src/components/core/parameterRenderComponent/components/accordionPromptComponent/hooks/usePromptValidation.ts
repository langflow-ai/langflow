import { type MutableRefObject, useEffect, useRef } from "react";
import { usePostValidatePrompt } from "@/controllers/API/queries/nodes/use-post-validate-prompt";
import type { APIClassType } from "@/types/api";

/**
 * Debounced prompt validation plus the double-bracket-mode
 * re-validation, moved verbatim from the component. Owns the
 * validate mutation and the timing refs; exposes
 * ``lastValidatedValueRef`` because the DOM-sync effect and the
 * modal setter reset it.
 */
export function usePromptValidation({
  value,
  internalValue,
  isDoubleBrackets,
  field_name,
  nodeClass,
  handleNodeClass,
}: {
  value: string;
  internalValue: string;
  isDoubleBrackets: boolean;
  field_name?: string;
  nodeClass?: APIClassType;
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  handleNodeClass?: (value: any, code?: string, type?: string) => void;
}): { lastValidatedValueRef: MutableRefObject<string> } {
  const { mutate: postValidatePrompt } = usePostValidatePrompt();
  const validateTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastValidatedValueRef = useRef<string>(value);

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

  return { lastValidatedValueRef };
}
