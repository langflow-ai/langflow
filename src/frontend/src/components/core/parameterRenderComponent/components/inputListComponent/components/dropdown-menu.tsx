import ForwardedIconComponent from "@/components/common/genericIconComponent";
import RenderIcons from "@/components/common/renderIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useKeyboardShortcut } from "@/hooks/use-overlap-shortcuts";
import { useShortcutsStore } from "@/stores/shortcuts";
import { cn } from "@/utils/utils";
import { useCallback } from "react";

export const DropdownMenuInputList = ({
  index,
  dropdownOpen,
  setDropdownOpen,
  editNode,
  handleDuplicateInput,
  removeInput,
}: {
  index: number;
  dropdownOpen: number | null;
  setDropdownOpen: (open: number) => void;
  editNode: boolean;
  handleDuplicateInput: (
    index: number,
    e: React.MouseEvent<HTMLDivElement> | KeyboardEvent,
  ) => void;
  removeInput: (
    index: number,
    e: React.MouseEvent<HTMLDivElement> | KeyboardEvent,
  ) => void;
}) => {
  const shortcuts = useShortcutsStore((state) => state.shortcuts);

  const shortcutKeys = {
    duplicate:
      shortcuts.find((obj) => obj.name === "Duplicate")?.shortcut || "",
    delete: shortcuts.find((obj) => obj.name === "Delete")?.shortcut || "",
  };

  const handleShortcut = useCallback(
    (shortcutName: string, event: KeyboardEvent) => {
      if (shortcutName === "duplicate") {
        handleDuplicateInput(index, event);
      } else if (shortcutName === "delete") {
        removeInput(index, event);
      }
      setDropdownOpen(-1);
    },
    [index, handleDuplicateInput, removeInput, setDropdownOpen],
  );

  useKeyboardShortcut({
    shortcutKeys,
    isEnabled: dropdownOpen === index,
    onShortcut: handleShortcut,
    preventDefault: true,
    stopPropagation: true,
  });

  return (
    <>
      <DropdownMenu
        open={dropdownOpen === index}
        onOpenChange={(open) => setDropdownOpen(open ? index : -1)}
      >
        <DropdownMenuTrigger
          asChild
          tabIndex={index}
          className="absolute translate-x-60 bg-background transition-opacity peer-focus:opacity-0"
        >
          <Button
            variant="ghost"
            data-testid={`input-list-dropdown-menu-${index}-${editNode ? "edit" : "view"}`}
            size={editNode ? "iconSm" : "iconMd"}
            className={cn("group", editNode ? "ml-4" : "")}
            autoFocus={false}
          >
            <ForwardedIconComponent
              name="Ellipsis"
              aria-hidden="true"
              className="h-5 w-5 text-muted-foreground group-hover:text-foreground"
            />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-[185px] translate-x-20" side="bottom">
          <DropdownMenuItem
            onClick={(e) => {
              handleDuplicateInput(index, e);
              e.stopPropagation();
            }}
            className="cursor-pointer"
            data-testid={`input-list-dropdown-menu-${index}-duplicate`}
          >
            <ForwardedIconComponent
              name="CopyPlus"
              aria-hidden="true"
              className="mr-2 h-4 w-4"
            />
            <span>Duplicate</span>

            <div className="flex grow content-end justify-end self-center text-[12px]">
              <span
                className={`flex content-end items-center rounded-sm bg-muted px-1.5 py-[0.1em] text-muted-foreground`}
              >
                <RenderIcons
                  filteredShortcut={shortcuts
                    .find((obj) => obj.name === "Duplicate")
                    ?.shortcut!?.split("+")}
                />
              </span>
            </div>
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={(e) => {
              removeInput(index, e);
              e.stopPropagation();
            }}
            className="cursor-pointer text-destructive"
            data-testid={`input-list-dropdown-menu-${index}-delete`}
          >
            <ForwardedIconComponent
              name="Trash2"
              aria-hidden="true"
              className="mr-2 h-4 w-4"
            />
            <span>Delete</span>

            <div className="flex grow content-end justify-end self-center text-[12px]">
              <span
                className={`flex content-end items-center rounded-sm px-1.5 py-[0.1em] text-muted-foreground`}
              >
                <ForwardedIconComponent
                  name="Delete"
                  className="h-4 w-4 stroke-2 text-red-400"
                />
              </span>
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
};
