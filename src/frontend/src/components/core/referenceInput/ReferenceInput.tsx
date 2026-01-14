import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import { ReferenceAutocomplete } from "./ReferenceAutocomplete";
import { parseReferences } from "@/utils/referenceParser";
import { getUpstreamOutputs } from "@/utils/getUpstreamOutputs";
import { getCaretCoordinates } from "@/utils/getCaretCoordinates";
import type { UpstreamOutput } from "@/types/references";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";

interface ReferenceInputProps {
  nodeId: string;
  value: string;
  onChange: (value: string, hasReferences: boolean) => void;
  className?: string;
  usePortal?: boolean;
  children: (props: {
    /** The current value to display (includes preview when navigating autocomplete) */
    value: string;
    /** The actual stored value (without preview) */
    actualValue: string;
    onChange: (
      e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
    ) => void;
    onKeyDown: (e: React.KeyboardEvent) => void;
    ref: React.RefObject<HTMLInputElement | HTMLTextAreaElement>;
  }) => ReactNode;
}

export function ReferenceInput({
  nodeId,
  value,
  onChange,
  className,
  usePortal = false,
  children,
}: ReferenceInputProps) {
  const [isAutocompleteOpen, setIsAutocompleteOpen] = useState(false);
  const [autocompleteFilter, setAutocompleteFilter] = useState("");
  const [autocompletePosition, setAutocompletePosition] = useState({
    top: 0,
    left: 0,
  });
  const [triggerIndex, setTriggerIndex] = useState<number | null>(null);
  const [isTextarea, setIsTextarea] = useState(false);
  // Track the currently highlighted option for preview
  const [previewOption, setPreviewOption] = useState<UpstreamOutput | null>(
    null,
  );

  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // Use a ref to track the current value to avoid stale closures
  const valueRef = useRef(value);
  const filterRef = useRef(autocompleteFilter);

  // Keep refs in sync with state/props
  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  useEffect(() => {
    filterRef.current = autocompleteFilter;
  }, [autocompleteFilter]);

  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const nodeReferenceSlugs = useFlowStore((state) => state.nodeReferenceSlugs);

  const upstreamOutputs = getUpstreamOutputs(
    nodeId,
    nodes,
    edges,
    nodeReferenceSlugs,
  );

  // Close autocomplete if upstream outputs become empty
  useEffect(() => {
    if (isAutocompleteOpen && upstreamOutputs.length === 0) {
      setIsAutocompleteOpen(false);
      setTriggerIndex(null);
    }
  }, [isAutocompleteOpen, upstreamOutputs.length]);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const newValue = e.target.value;
      const cursorPos = e.target.selectionStart || 0;

      // Update filter text when autocomplete is open
      if (isAutocompleteOpen && triggerIndex !== null) {
        // Update filter with text after @
        const filterText = newValue.slice(triggerIndex + 1, cursorPos);
        if (filterText.includes(" ") || cursorPos <= triggerIndex) {
          // Close if space typed or cursor moved before @
          setIsAutocompleteOpen(false);
          setTriggerIndex(null);
          setPreviewOption(null);
        } else {
          setAutocompleteFilter(filterText);
        }
      }

      // Check if value has references
      const refs = parseReferences(newValue);
      onChange(newValue, refs.length > 0);
    },
    [isAutocompleteOpen, triggerIndex, onChange],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      // Detect @ key press to open autocomplete
      if (e.key === "@" && !isAutocompleteOpen && upstreamOutputs.length > 0) {
        const target = e.target as HTMLInputElement | HTMLTextAreaElement;
        const cursorPos = target.selectionStart ?? 0;

        // Set trigger index to where @ will be inserted
        setTriggerIndex(cursorPos);
        setAutocompleteFilter("");
        setIsAutocompleteOpen(true);

        const isTextareaElement = target.tagName === "TEXTAREA";
        setIsTextarea(isTextareaElement);

        // Position the dropdown
        // Need to wait for the @ to be inserted before calculating position
        requestAnimationFrame(() => {
          if (isTextareaElement) {
            const caretCoords = getCaretCoordinates(target, cursorPos + 1);
            const scrollTop = target.scrollTop;
            setAutocompletePosition({
              top: caretCoords.top - scrollTop + caretCoords.height + 4,
              left: caretCoords.left,
            });
          } else {
            const rect = target.getBoundingClientRect();
            setAutocompletePosition({
              top: rect.height + 4,
              left: 0,
            });
          }
        });
      }

      if (isAutocompleteOpen) {
        if (["ArrowDown", "ArrowUp", "Enter", "Escape"].includes(e.key)) {
          // Let autocomplete handle these
          return;
        }
      }
    },
    [isAutocompleteOpen, upstreamOutputs.length],
  );

  const handleSelectReference = useCallback(
    (option: UpstreamOutput) => {
      if (triggerIndex === null) {
        return;
      }

      // Use refs to get the current value (avoids stale closure issues)
      const currentValue = valueRef.current;
      const currentFilter = filterRef.current;

      // Calculate cursor position based on triggerIndex + filter length + 1 (for the @)
      const cursorPos = triggerIndex + 1 + currentFilter.length;
      const before = currentValue.slice(0, triggerIndex);
      const after = currentValue.slice(cursorPos);
      const reference = `@${option.nodeSlug}.${option.outputName}`;

      const newValue = before + reference + after;

      // Check if new value has references
      const refs = parseReferences(newValue);
      onChange(newValue, refs.length > 0);

      setIsAutocompleteOpen(false);
      setTriggerIndex(null);
      setAutocompleteFilter("");
    },
    [triggerIndex, onChange],
  );

  const handleCloseAutocomplete = useCallback(() => {
    setIsAutocompleteOpen(false);
    setTriggerIndex(null);
    setPreviewOption(null);
  }, []);

  // Callback when the highlighted option changes in autocomplete
  const handleHighlightChange = useCallback((option: UpstreamOutput | null) => {
    setPreviewOption(option);
  }, []);

  // Calculate the display value with preview
  const displayValue = (() => {
    if (!isAutocompleteOpen || !previewOption || triggerIndex === null) {
      return value;
    }
    // Show preview: replace @filter with @nodeSlug.outputName
    const before = value.slice(0, triggerIndex);
    const cursorPos = triggerIndex + 1 + autocompleteFilter.length;
    const after = value.slice(cursorPos);
    const preview = `@${previewOption.nodeSlug}.${previewOption.outputName}`;
    return before + preview + after;
  })();

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {children({
        value: displayValue,
        actualValue: value,
        onChange: handleInputChange,
        onKeyDown: handleKeyDown,
        ref: inputRef as React.RefObject<
          HTMLInputElement | HTMLTextAreaElement
        >,
      })}
      <ReferenceAutocomplete
        isOpen={isAutocompleteOpen}
        options={upstreamOutputs}
        onSelect={handleSelectReference}
        onClose={handleCloseAutocomplete}
        onHighlightChange={handleHighlightChange}
        filter={autocompleteFilter}
        position={autocompletePosition}
        anchorRef={usePortal ? containerRef : undefined}
        inputRef={usePortal ? inputRef : undefined}
        isTextarea={isTextarea}
      />
    </div>
  );
}
