import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import useFlowStore from "@/stores/flowStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import { getCaretCoordinates } from "@/utils/getCaretCoordinates";
import { getUpstreamOutputs } from "@/utils/getUpstreamOutputs";
import { parseReferences } from "@/utils/referenceParser";
import { cn } from "@/utils/utils";
import { ReferenceAutocomplete } from "./ReferenceAutocomplete";

interface ReferenceInputProps {
  nodeId: string;
  value: string;
  onChange: (value: string, hasReferences: boolean) => void;
  className?: string;
  usePortal?: boolean;
  children: (props: {
    value: string;
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
  const globalVariables = useGlobalVariablesStore(
    (state) => state.globalVariablesEntities,
  );

  const upstreamOutputs = useMemo(
    () =>
      getUpstreamOutputs(
        nodeId,
        nodes,
        edges,
        nodeReferenceSlugs,
        globalVariables ?? undefined,
      ),
    [nodeId, nodes, edges, nodeReferenceSlugs, globalVariables],
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
    (e: React.KeyboardEvent) => {
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
  }, []);

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {children({
        value,
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
        filter={autocompleteFilter}
        position={autocompletePosition}
        anchorRef={usePortal ? containerRef : undefined}
        inputRef={usePortal ? inputRef : undefined}
        isTextarea={isTextarea}
      />
    </div>
  );
}
