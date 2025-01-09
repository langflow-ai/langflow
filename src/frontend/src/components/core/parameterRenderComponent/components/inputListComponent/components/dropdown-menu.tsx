import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/utils/utils";

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
    e: React.MouseEvent<HTMLDivElement>,
  ) => void;
  removeInput: (index: number, e: React.MouseEvent<HTMLDivElement>) => void;
}) => {
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
            Duplicate
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
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );
};
