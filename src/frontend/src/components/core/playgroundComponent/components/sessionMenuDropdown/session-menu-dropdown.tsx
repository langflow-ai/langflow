import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SessionMenuItem } from "./components/session-menu-item";

export function SessionMenuDropdown({
  children,
  onRename,
  onDelete,
  onLogs,
}: {
  children: React.ReactNode;
  onRename?: () => void;
  onDelete?: () => void;
  onLogs: () => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent>
        {onRename && (
          <SessionMenuItem onSelect={onRename} icon="Pencil">
            Rename
          </SessionMenuItem>
        )}
        <SessionMenuItem onSelect={onLogs} icon="ScrollText">
          Session logs
        </SessionMenuItem>
        {onDelete && (
          <SessionMenuItem
            onSelect={onDelete}
            icon="Trash"
            className="text-destructive"
          >
            Delete session
          </SessionMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
