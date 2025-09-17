import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

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
  const formattedIcon =
    item?.icon?.charAt(0).toUpperCase() + item?.icon?.slice(1);

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
        "group flex w-full rounded-md px-2 py-0.5",
        !isKeyboardNavActive && "hover:bg-muted", // Only apply hover styles when not in keyboard nav
        !item.metaData && "py-2.5",
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
      <div className="flex w-full items-center gap-3">
        {item.icon && (
          <div>
            <ForwardedIconComponent name={formattedIcon} className="h-4 w-4" />
          </div>
        )}
        <div className="flex w-full flex-col truncate">
          <div className="flex w-full items-center gap-2 truncate text-mmd font-medium">
            <span className="truncate">{item.name}</span>
            {"description" in item && item.description && (
              <span className="font-normal text-muted-foreground">
                {item.description}
              </span>
            )}
          </div>
          {"metaData" in item && item.metaData && (
            <div className="flex w-full truncate text-mmd text-gray-500">
              <span className="truncate">{item.metaData}</span>
            </div>
          )}
        </div>

        {isHovered || isFocused ? (
          <div className="ml-auto flex items-center justify-start rounded-md">
            <div className="flex items-center pr-1.5 text-mmd font-semibold text-muted-foreground">
              Select
            </div>
            <div className="flex items-center justify-center rounded-md">
              <ForwardedIconComponent
                name="corner-down-left"
                className="h-3.5 w-3.5 text-muted-foreground"
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

export default ListItem;
