import type React from "react";
import { useMemo } from "react";
import { useShallow } from "zustand/react/shallow";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  NO_SESSIONS_MATCH_SEARCH,
  SEARCH_SESSIONS,
} from "@/constants/constants";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { useSearch } from "@/hooks/useSearch";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { SessionItem } from "./session-item";

interface SessionManagerDropdownProps {
  children: React.ReactNode;
}

export const SessionManagerDropdown = ({
  children,
}: SessionManagerDropdownProps) => {
  const { isPlayground } = usePlaygroundStore();

  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );

  const { data: dbSessions } = useGetSessionsFromFlowQuery({
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

  const sessions = useMemo(() => {
    if (!selectedSession || dbSessions?.includes(selectedSession)) {
      return dbSessions;
    }
    return [...(dbSessions || []), selectedSession];
  }, [dbSessions, selectedSession]);

  const {
    query,
    setQuery,
    filteredItems: filteredSessions,
  } = useSearch(sessions || []);

  const handleRename = (oldSessionId: string, newSessionId: string) => {
    if (!selectedSession) {
      return;
    }
    if (dbSessions?.includes(selectedSession)) {
      updateSessionName({
        oldSessionId,
        newSessionId,
      });
    }
    if (oldSessionId === selectedSession) {
      setSelectedSession(newSessionId);
    }
  };

  const handleDelete = (sessionId: string) => {
    if (selectedSession === sessionId) {
      setSelectedSession(flowId);
    }
    if (dbSessions?.includes(sessionId)) {
      deleteSession({ sessionId });
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setQuery("");
    }
  };

  return (
    <DropdownMenu onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent className="w-80 p-0" align="start">
        {sessions && (
          <>
            <div className="p-1 border-b">
              <Input
                placeholder={SEARCH_SESSIONS}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="h-8 text-sm"
                icon="Search"
                autoFocus
                inputClassName="h-8 text-sm border-none"
              />
            </div>
            <div className="max-h-64 overflow-y-auto">
              {filteredSessions.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  {NO_SESSIONS_MATCH_SEARCH}
                </div>
              ) : (
                filteredSessions.map((sessionId, index) => (
                  <SessionItem
                    key={sessionId}
                    tabIndex={index}
                    sessionId={sessionId}
                    onRename={handleRename}
                    onDelete={handleDelete}
                  />
                ))
              )}
            </div>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
