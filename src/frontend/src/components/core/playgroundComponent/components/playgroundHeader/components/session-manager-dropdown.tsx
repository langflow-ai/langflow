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
import { NEW_SESSION_NAME } from "@/constants/constants";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useGetAddSessions } from "../../../hooks/use-get-add-sessions";
import { SessionItem } from "./session-manager-item";
import { SessionMenuItem } from "./session-menu-item";

interface SessionManagerDropdownProps {
  children: React.ReactNode;
}

export const SessionManagerDropdown = ({
  children,
}: SessionManagerDropdownProps) => {
  const { sessions, addNewSession } = useGetAddSessions();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {sessions && (
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
