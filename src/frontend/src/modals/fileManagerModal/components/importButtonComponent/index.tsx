import { DropdownMenuItem } from "@/components/ui/dropdown-menu";

import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function ImportButtonComponent({
  children,
}: {
  children?: React.ReactNode;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {children ?? (
          <Button size="sm" className="font-semibold">
            Import from...
            <ForwardedIconComponent
              name="ChevronDown"
              className="ml-2 h-4 w-4"
            />
          </Button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="-mr-0 p-1">
        <DropdownMenuItem className="cursor-pointer gap-2">
          <ForwardedIconComponent name="GoogleDrive" className="h-4 w-4" />
          Drive
        </DropdownMenuItem>
        <DropdownMenuItem className="cursor-pointer gap-2">
          <ForwardedIconComponent name="OneDrive" className="h-4 w-4" />
          OneDrive
        </DropdownMenuItem>
        <DropdownMenuItem className="cursor-pointer gap-2">
          <ForwardedIconComponent name="Dropbox" className="h-4 w-4" />
          Dropbox
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
