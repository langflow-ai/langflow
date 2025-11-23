import type React from "react";
import { useShallow } from "zustand/react/shallow";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import useFlowStore from "@/stores/flowStore";
import { useGetAddSessions } from "../../hooks/use-get-add-sessions";
import { SessionMenuItem } from "../sessionMenuDropdown/components/session-menu-item";
import { SessionItem } from "./components/session-manager-item";

interface SessionManagerDropdownProps {
  children: React.ReactNode;
}

export const SessionManagerDropdown = ({
  children,
}: SessionManagerDropdownProps) => {
  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));
  const { sessions, addNewSession } = useGetAddSessions({ flowId });

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {sessions && (
          <>
            <DropdownMenuGroup>
              {sessions?.map((session) => (
                <SessionItem key={session.id} sessionId={session.sessionId} />
              ))}
            </DropdownMenuGroup>
            <DropdownMenuSeparator className="!my-0" />
            <DropdownMenuGroup>
              <SessionMenuItem
                onSelect={addNewSession ?? (() => {})}
                icon="Plus"
                disabled={addNewSession === undefined}
              >
                New Session
              </SessionMenuItem>
            </DropdownMenuGroup>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
