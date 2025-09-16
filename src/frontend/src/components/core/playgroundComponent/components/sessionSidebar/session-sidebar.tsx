import { useShallow } from "zustand/react/shallow";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import useFlowStore from "@/stores/flowStore";
import { useEditSessionInfo } from "../../hooks/use-edit-session-info";
import { useGetAddSessions } from "../../hooks/use-get-add-sessions";
import { SessionItem } from "./components/session-item";
import { SessionSkeleton } from "./components/session-skeleton";

export default function SessionSidebar() {
  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));

  const { sessions, addNewSession } = useGetAddSessions({ flowId });
  const { handleRename, handleDelete } = useEditSessionInfo({
    flowId,
  });

  return (
    <div className="flex h-full">
      <div className="flex flex-col h-full w-[250px] p-4 gap-1">
        <div className="flex w-full items-center justify-between px-2 pt-1">
          <span className="text-xs font-semibold text-muted-foreground">
            Sessions
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={addNewSession}
            disabled={addNewSession === undefined}
          >
            <ForwardedIconComponent
              name="Plus"
              className="w-4 h-4 text-muted-foreground"
            />
          </Button>
        </div>
        {sessions ? (
          sessions.map((session) => (
            <SessionItem
              key={session.id}
              sessionId={session.sessionId}
              onRename={handleRename}
              onDelete={handleDelete}
            />
          ))
        ) : (
          <SessionSkeleton />
        )}
      </div>
      <Separator orientation="vertical" className="shrink-0" />
    </div>
  );
}
