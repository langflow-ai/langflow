import React from "react";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useShallow } from "zustand/react/shallow";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { SessionItem } from "./session-item";
import { useSearch } from "@/hooks/useSearch";

interface SessionManagerPopoverProps {
  children: React.ReactNode;
}

export const SessionManagerPopover = ({
  children,
}: SessionManagerPopoverProps) => {
  const { isPlayground } = usePlaygroundStore();

  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));

  const { data: sessions } = useGetSessionsFromFlowQuery({
    flowId,
    useLocalStorage: isPlayground,
  });

  const { mutate: updateSessionName } = useUpdateSessionName({
    flowId,
    useLocalStorage: isPlayground,
  });

  const { mutate: deleteSession } = useDeleteSession({
    flowId,
    useLocalStorage: isPlayground,
  });

  const {
    query,
    setQuery,
    filteredItems: filteredSessions,
  } = useSearch(sessions || []);

  const handleRename = (oldSessionId: string, newSessionId: string) => {
    updateSessionName({
      oldSessionId,
      newSessionId,
    });
  };

  const handleDelete = (sessionId: string) => {
    deleteSession({ sessionId });
  };

  return (
    <Popover>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="start">
        {sessions && (
          <>
            <div className="p-3 border-b">
              <Input
                placeholder="Search sessions..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="h-8 text-sm"
              />
            </div>
            <div className="max-h-64 overflow-y-auto">
              {filteredSessions.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  {query
                    ? "No sessions match your search"
                    : "No sessions found"}
                </div>
              ) : (
                filteredSessions.map((sessionId) => (
                  <SessionItem
                    key={sessionId}
                    sessionId={sessionId}
                    onRename={handleRename}
                    onDelete={handleDelete}
                  />
                ))
              )}
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
};
