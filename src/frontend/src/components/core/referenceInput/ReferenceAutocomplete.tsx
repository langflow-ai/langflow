import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { UpstreamOutput } from "@/types/references";
import { cn } from "@/utils/utils";

interface ReferenceAutocompleteProps {
  isOpen: boolean;
  options: UpstreamOutput[];
  onSelect: (option: UpstreamOutput) => void;
  onClose: () => void;
  filter: string;
  position: { top: number; left: number };
  anchorRef?: React.RefObject<HTMLElement | null>;
  inputRef?: React.RefObject<HTMLElement | null>;
  isTextarea?: boolean;
}

export function ReferenceAutocomplete({
  isOpen,
  options,
  onSelect,
  onClose,
  filter,
  position,
  anchorRef,
  inputRef,
  isTextarea = false,
}: ReferenceAutocompleteProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const [portalPosition, setPortalPosition] = useState({ top: 0, left: 0 });

  // Update portal position based on input element + caret position
  useEffect(() => {
    if (isOpen && anchorRef) {
      // Use inputRef if available (for accurate caret positioning), otherwise fall back to anchorRef
      const element = inputRef?.current || anchorRef?.current;
      if (element) {
        const rect = element.getBoundingClientRect();
        // position.top and position.left are relative to the input element
        setPortalPosition({
          top: rect.top + position.top,
          left: rect.left + position.left,
        });
      }
    }
  }, [isOpen, anchorRef, inputRef, position]);

  // Memoize filtered options to avoid new array reference on every render
  const filteredOptions = useMemo(() => {
    const lowerFilter = filter.toLowerCase();
    return options.filter((opt) => {
      const searchText =
        `${opt.nodeName} ${opt.outputName} ${opt.nodeSlug}`.toLowerCase();
      return searchText.includes(lowerFilter);
    });
  }, [options, filter]);

  // Reset selection when filter changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [filter]);

  // Scroll selected item into view
  useEffect(() => {
    if (!isOpen || !listRef.current) return;
    const selectedEl = listRef.current.children[selectedIndex] as
      | HTMLElement
      | undefined;
    selectedEl?.scrollIntoView?.({ block: "nearest" });
  }, [isOpen, selectedIndex]);

  // Keyboard navigation — only register when open
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setSelectedIndex((i) => Math.min(i + 1, filteredOptions.length - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setSelectedIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
          e.preventDefault();
          if (filteredOptions[selectedIndex]) {
            onSelect(filteredOptions[selectedIndex]);
          }
          break;
        case "Escape":
          e.preventDefault();
          onClose();
          break;
      }
    },
    [filteredOptions, selectedIndex, onSelect, onClose],
  );

  useEffect(() => {
    if (!isOpen) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleKeyDown]);

  if (!isOpen || filteredOptions.length === 0) return null;

  // Determine positioning style based on rendering mode
  function getPositionStyle(): React.CSSProperties {
    // Portal mode: use fixed positioning with calculated coordinates
    if (anchorRef) {
      return { top: portalPosition.top, left: portalPosition.left };
    }
    // Textarea: position at caret location
    if (isTextarea) {
      return { top: position.top, left: position.left };
    }
    // Input: position below the container
    return { top: "100%", left: 0, marginTop: 4 };
  }

  const dropdown = (
    <div
      ref={listRef}
      role="listbox"
      aria-label="Reference suggestions"
      data-testid="reference-autocomplete-dropdown"
      className={cn(
        "z-[9999] w-64 max-h-48 overflow-auto bg-background border border-border rounded-md shadow-lg",
        anchorRef ? "fixed" : "absolute",
      )}
      style={getPositionStyle()}
    >
      {filteredOptions.map((option, index) => (
        <button
          key={`${option.nodeId}-${option.outputName}`}
          type="button"
          role="option"
          aria-selected={index === selectedIndex}
          data-testid={`reference-option-${option.nodeSlug}-${option.outputName}`}
          className={cn(
            "w-full px-3 py-2 text-left text-sm cursor-pointer",
            "hover:bg-muted",
            index === selectedIndex && "bg-muted",
          )}
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onSelect(option);
          }}
        >
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center">
              <span className="font-medium">{option.nodeName}</span>
              <span className="text-muted-foreground mx-1">→</span>
              <span>{option.outputDisplayName}</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {option.outputType}
              </span>
            </div>
            <code className="text-xs text-muted-foreground font-mono">
              @{option.nodeSlug}.{option.outputName}
            </code>
          </div>
        </button>
      ))}
    </div>
  );

  // Use portal when anchorRef is provided (for modals), otherwise render inline
  if (anchorRef) {
    return createPortal(dropdown, document.body);
  }

  return dropdown;
}
