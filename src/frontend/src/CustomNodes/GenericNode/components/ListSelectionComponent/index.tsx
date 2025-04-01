import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import SearchBarComponent from "@/components/core/parameterRenderComponent/components/searchBarComponent";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog-with-no-close";
import { cn } from "@/utils/utils";
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
}: {
  item: any;
  isSelected: boolean;
  onClick: () => void;
  className?: string;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  isFocused: boolean;
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const itemRef = useRef<HTMLButtonElement>(null);

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
      unstyled
      size="sm"
      className={cn(
        "group w-full rounded-md py-3 pl-3 pr-3 hover:bg-muted",
        isFocused && "bg-muted",
        className,
      )}
      onClick={onClick}
      onMouseEnter={() => {
        setIsHovered(true);
        onMouseEnter();
      }}
      onMouseLeave={() => {
        setIsHovered(false);
        onMouseLeave();
      }}
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
            <div className="flex items-center pr-1.5 text-sm text-gray-500">
              Select
            </div>
            <div className="flex items-center justify-center rounded-md bg-gray-200 p-1">
              <ForwardedIconComponent
                name="corner-down-left"
                className="h-3 w-3 text-gray-500"
              />
            </div>
          </div>
        ) : (
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

  const filteredList = useMemo(() => {
    if (!search.trim()) {
      return options;
    }
    const searchTerm = search.toLowerCase();
    return options.filter((item) =>
      item.name.toLowerCase().includes(searchTerm),
    );
  }, [options, search]);

  useEffect(() => {
    // Reset search and focus when dialog opens or filtered list changes
    if (open) {
      setSearch("");
      setHoveredItem(null);
      if (filteredList.length > 0) {
        setFocusedIndex(0);
        setHoveredItem(filteredList[0]);
      } else {
        setFocusedIndex(-1);
      }
    }
  }, [open, filteredList.length]);

  // Handle keyboard events
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!open || filteredList.length === 0) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setFocusedIndex((prev) => {
            const newIndex = prev < filteredList.length - 1 ? prev + 1 : 0;
            setHoveredItem(filteredList[newIndex]);
            return newIndex;
          });
          break;
        case "ArrowUp":
          e.preventDefault();
          setFocusedIndex((prev) => {
            const newIndex = prev > 0 ? prev - 1 : filteredList.length - 1;
            setHoveredItem(filteredList[newIndex]);
            return newIndex;
          });
          break;
        case "Enter":
          if (hoveredItem) {
            handleSelectAction(hoveredItem);
            onSelection?.(hoveredItem);
          }
          break;
      }
    };

    if (open) {
      window.addEventListener("keydown", handleKeyDown);
    }

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, filteredList, hoveredItem, focusedIndex]);

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

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="flex max-h-[65vh] min-h-[30vh] flex-col rounded-xl">
        <div className="flex items-center justify-between pb-4">
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

        <div className="flex flex-col gap-1 overflow-y-auto">
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
                }}
                onMouseLeave={() => {
                  setHoveredItem(null);
                  // Don't reset focused index on mouse leave
                }}
                isFocused={focusedIndex === index}
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
