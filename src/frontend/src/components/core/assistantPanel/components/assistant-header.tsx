import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ASSISTANT_TITLE } from "../assistant-panel.constants";

interface AssistantHeaderProps {
  onClose: () => void;
  onNewSession: () => void;
  hasMessages: boolean;
}

export function AssistantHeader({
  onClose,
  onNewSession,
  hasMessages,
}: AssistantHeaderProps) {
  return (
    <div className="flex h-12 items-center justify-between px-4">
      <h2 className="text-sm font-medium text-foreground">{ASSISTANT_TITLE}</h2>
      <div className="flex items-center">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              title="Options"
            >
              <ForwardedIconComponent
                name="MoreVertical"
                className="h-4 w-4 text-muted-foreground"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="z-[70]">
            <DropdownMenuItem onClick={onNewSession} disabled={!hasMessages}>
              <ForwardedIconComponent name="Plus" className="mr-2 h-4 w-4" />
              New session
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          title="Close"
          onClick={onClose}
        >
          <ForwardedIconComponent
            name="X"
            className="h-4 w-4 text-muted-foreground"
          />
        </Button>
      </div>
    </div>
  );
}
