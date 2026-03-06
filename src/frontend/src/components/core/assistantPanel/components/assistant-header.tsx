import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
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
        <Button
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 px-2 text-sm text-muted-foreground hover:text-foreground"
          onClick={onNewSession}
          disabled={!hasMessages}
        >
          <ForwardedIconComponent name="Plus" className="h-4 w-4" />
          New session
        </Button>

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
