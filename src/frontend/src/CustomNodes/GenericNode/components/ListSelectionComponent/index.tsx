import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import SearchBarComponent from "@/components/core/parameterRenderComponent/components/searchBarComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close";
import { cn, testIdCase } from "@/utils/utils";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// Update interface with better types
interface ListSelectionComponentProps {
  open: boolean;
  onClose: () => void;
  options: any[];
  setSelectedList: (action: any[]) => void;
  selectedList: any[];
  searchCategories?: string[];
  onSelection?: (action: any) => void;
  limit?: number;
}

const ListItem = ({
  item,
  isSelected,
  onClick,
  className,
  onMouseEnter,
  onMouseLeave,
  isFocused,
  isKeyboardNavActive,
  dataTestId,
}: {
  item: any;
  isSelected: boolean;
  onClick: () => void;
  className?: string;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  isFocused: boolean;
  isKeyboardNavActive: boolean;
  dataTestId: string;
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const itemRef = useRef<HTMLButtonElement>(null);

  // Clear hover state when keyboard navigation is active
  useEffect(() => {
    if (isKeyboardNavActive) {
      setIsHovered(false);
    }
  }, [isKeyboardNavActive]);

  // Scroll into view when focused by keyboard
  useEffect(() => {
    if (isFocused && itemRef.current) {
      itemRef.current.scrollIntoView({ block: "nearest" });
    }
  }, [isFocused]);

  return (
    <Button
      ref={itemRef}
      key={item.id}
      data-testid={dataTestId}
      unstyled
      size="sm"
      className={cn(
        "group w-full rounded-md py-3 pl-3 pr-3",
        !isKeyboardNavActive && "hover:bg-muted", // Only apply hover styles when not in keyboard nav
        isFocused && "bg-muted",
        className,
      )}
      onClick={onClick}
      onMouseEnter={() => {
        if (!isKeyboardNavActive) {
          setIsHovered(true);
          onMouseEnter();
        }
      }}
      onMouseLeave={() => {
        setIsHovered(false);
        onMouseLeave();
      }}
      // Disable pointer events during keyboard navigation
      style={{ pointerEvents: isKeyboardNavActive ? "none" : "auto" }}
    >
      <div className="flex w-full items-center gap-2">
        {item.icon && (
          <ForwardedIconComponent name={item.icon} className="h-5 w-5" />
        )}
        <div className="truncate text-sm">{item.name}</div>
        {"metaData" in item && item.metaData && (
          <div className="text-gray-500">{item.metaData}</div>
        )}
        {isHovered || isFocused ? (
          <div className="ml-auto flex items-center justify-start rounded-md">
            <div className="flex items-center pr-1.5 text-sm text-muted-foreground">
              Select
            </div>
            <div className="flex items-center justify-center rounded-md bg-border p-1">
              <ForwardedIconComponent
                name="corner-down-left"
                className="h-3 w-3 text-muted-foreground"
              />
            </div>
          </div>
        ) : (
          // Always show the check icon when selected, regardless of hover/focus state
          isSelected && (
            <ForwardedIconComponent
              name="check"
              className={cn(
                "ml-auto flex h-4 w-4",
                item.link === "validated" && "text-green-500",
              )}
            />
          )
        )}
      </div>
    </Button>
  );
};

const ListSelectionComponent = ({
  open,
  onClose,
  searchCategories = [],
  onSelection,
  setSelectedList = () => {},
  selectedList = [],
  options,
  limit = 1,
}: ListSelectionComponentProps) => {
  const [search, setSearch] = useState("");
  const [hoveredItem, setHoveredItem] = useState<any | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const [isKeyboardNavActive, setIsKeyboardNavActive] = useState(false);
  const listContainerRef = useRef<HTMLDivElement>(null);

  const filteredList = useMemo(() => {
    if (!search.trim()) {
      return options;
    }
    const searchTerm = search.toLowerCase();
    return options.filter((item) =>
      item.name.toLowerCase().includes(searchTerm),
    );
  }, [options, search]);

  const handleSelectAction = useCallback(
    (action: any) => {
      if (limit !== 1) {
        // Multiple selection mode
        const isAlreadySelected = selectedList.some(
          (selectedItem) => selectedItem.name === action.name,
        );

        if (isAlreadySelected) {
          setSelectedList(
            selectedList.filter(
              (selectedItem) => selectedItem.name !== action.name,
            ),
          );
        } else {
          // Check if we've reached the selection limit
          if (selectedList.length < limit) {
            setSelectedList([...selectedList, action]);
          }
        }
      } else {
        // Single selection mode
        setSelectedList([
          {
            name: action.name,
            icon: "icon" in action ? action.icon : undefined,
            link: "link" in action ? action.link : undefined,
          },
        ]);
        onClose();
      }
    },
    [selectedList, setSelectedList, limit, onClose],
  );

  // Reset focus state when filtered list changes
  useEffect(() => {
    if (open) {
      if (filteredList.length > 0) {
        setFocusedIndex(0);
        setHoveredItem(filteredList[0]);
      } else {
        setFocusedIndex(-1);
        setHoveredItem(null);
      }
    }
  }, [open, filteredList.length]);

  // Reset search when dialog opens
  useEffect(() => {
    if (open) {
      setSearch("");
      setIsKeyboardNavActive(false);
    }
  }, [open]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (filteredList.length === 0) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setIsKeyboardNavActive(true);
          setFocusedIndex((prev) => {
            const newIndex = prev < filteredList.length - 1 ? prev + 1 : 0;
            setHoveredItem(filteredList[newIndex]);
            return newIndex;
          });
          break;
        case "ArrowUp":
          e.preventDefault();
          setIsKeyboardNavActive(true);
          setFocusedIndex((prev) => {
            const newIndex = prev > 0 ? prev - 1 : filteredList.length - 1;
            setHoveredItem(filteredList[newIndex]);
            return newIndex;
          });
          break;
        case "Enter":
          if (hoveredItem) {
            e.preventDefault();
            handleSelectAction(hoveredItem);
            if (onSelection) {
              onSelection(hoveredItem);
            }
          }
          break;
        case "Escape":
          e.preventDefault();
          onClose();
          break;
      }
    },
    [filteredList, hoveredItem, handleSelectAction, onSelection, onClose],
  );

  // Detect mouse movement to switch from keyboard to mouse navigation
  useEffect(() => {
    const handleMouseMove = () => {
      if (isKeyboardNavActive) {
        setIsKeyboardNavActive(false);
      }
    };

    if (open) {
      window.addEventListener("mousemove", handleMouseMove);
      return () => {
        window.removeEventListener("mousemove", handleMouseMove);
      };
    }
  }, [open, isKeyboardNavActive]);

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent
        className="flex max-h-[65vh] min-h-[15vh] flex-col rounded-xl"
        onKeyDown={handleKeyDown}
      >
        <div className="flex items-center justify-between">
          <SearchBarComponent
            searchCategories={searchCategories}
            search={search}
            setSearch={setSearch}
          />
          <Button
            unstyled
            size="icon"
            className="ml-auto h-[38px]"
            onClick={onClose}
          >
            <ForwardedIconComponent name="x" />
          </Button>
        </div>

        <div
          ref={listContainerRef}
          className="flex flex-col gap-1 overflow-y-auto"
        >
          {filteredList.length > 0 ? (
            filteredList.map((item, index) => (
              <ListItem
                key={`${item.name}-${index}`}
                item={item}
                isSelected={
                  selectedList.some(
                    (selected) => selected.name === item.name,
                  ) || item.link === "validated"
                }
                onClick={() => {
                  handleSelectAction(item);
                  onSelection?.(item);
                }}
                onMouseEnter={() => {
                  setHoveredItem(item);
                  setFocusedIndex(index);
                  setIsKeyboardNavActive(false);
                }}
                onMouseLeave={() => {
                  setHoveredItem(null);
                  // Don't reset focused index on mouse leave
                }}
                isFocused={focusedIndex === index}
                isKeyboardNavActive={isKeyboardNavActive}
                dataTestId={`list_item_${testIdCase(item.name)}`}
              />
            ))
          ) : (
            <div className="py-3 text-center text-gray-500">
              No items match your search
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ListSelectionComponent;
