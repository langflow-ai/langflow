import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { translateComponentMetadata } from "@/utils/component-metadata-i18n";
import { cn } from "@/utils/utils";

type ListSelectionItem = {
  id?: string;
  name: string;
  description?: string;
  icon?: string;
  link?: string;
  metaData?: string;
};

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
  item: ListSelectionItem;
  isSelected: boolean;
  onClick: () => void;
  className?: string;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  isFocused: boolean;
  isKeyboardNavActive: boolean;
  dataTestId: string;
}) => {
  const { t } = useTranslation();
  const [isHovered, setIsHovered] = useState(false);
  const itemRef = useRef<HTMLButtonElement>(null);
  const formattedIcon =
    item?.icon?.charAt(0).toUpperCase() + item?.icon?.slice(1);
  const translatedName = translateComponentMetadata(t, "action", item.name);
  const translatedDescription = item.description
    ? translateComponentMetadata(t, "info", item.description)
    : undefined;

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
            <span className="truncate">{translatedName}</span>
            {translatedDescription && (
              <span className="font-normal text-muted-foreground">
                {translatedDescription}
              </span>
            )}
          </div>
          {"metaData" in item && item.metaData && (
            <div className="flex w-full truncate text-mmd text-muted-foreground">
              <span className="truncate">{item.metaData}</span>
            </div>
          )}
        </div>

        {isHovered || isFocused ? (
          <div className="ml-auto flex items-center justify-start rounded-md">
            <div className="flex items-center pr-1.5 text-mmd font-semibold text-muted-foreground">
              {t("common.select")}
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
                item.link === "validated" && "text-accent-emerald-foreground",
              )}
            />
          )
        )}
      </div>
    </Button>
  );
};

export default ListItem;
