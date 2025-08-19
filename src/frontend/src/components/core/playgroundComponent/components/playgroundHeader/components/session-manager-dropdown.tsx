import type React from "react";
import { useMemo } from "react";
import { useShallow } from "zustand/react/shallow";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { SessionItem } from "./session-manager-item";
import { SessionMenuItem } from "./session-menu-item";

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

  const addNewSession = () => {
    const newSessionId = `New Chat ${dbSessions?.length ?? 0}`;
    setSelectedSession(newSessionId);
  };

  const sessions = useMemo(() => {
    if (!selectedSession || dbSessions?.includes(selectedSession)) {
      return dbSessions;
    }
    return [...(dbSessions || []), selectedSession];
  }, [dbSessions, selectedSession]);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {dbSessions && (
          <>
            <DropdownMenuGroup>
              {sessions?.map((sessionId) => (
                <SessionItem key={sessionId} sessionId={sessionId} />
              ))}
            </DropdownMenuGroup>
            <DropdownMenuSeparator className="!my-0" />
            <DropdownMenuGroup>
              <SessionMenuItem onSelect={addNewSession} icon="Plus">
                New Session
              </SessionMenuItem>
            </DropdownMenuGroup>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
