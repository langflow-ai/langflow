import { forwardRef } from "react";
import { useShallow } from "zustand/react/shallow";
import { DEFAULT_SESSION_NAME } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { cn } from "@/utils/utils";
import { SessionMenuItem } from "../../sessionMenuDropdown/components/session-menu-item";

interface SessionItemProps {
  sessionId: string;
}

export const SessionItem = forwardRef<HTMLDivElement, SessionItemProps>(
  ({ sessionId }, ref) => {
    const selectedSession = usePlaygroundStore(
      (state) => state.selectedSession
    );
    const setSelectedSession = usePlaygroundStore(
      (state) => state.setSelectedSession
    );

    const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));

    const handleSessionSelect = () => {
      setSelectedSession(sessionId);
    };
    const isSelected = selectedSession === sessionId;
    const canEdit = sessionId !== flowId;

    return (
      <SessionMenuItem
        className={cn(isSelected && "bg-muted")}
        onSelect={handleSessionSelect}
        ref={ref}
      >
        {canEdit ? sessionId : DEFAULT_SESSION_NAME}
      </SessionMenuItem>
    );
  }
);
