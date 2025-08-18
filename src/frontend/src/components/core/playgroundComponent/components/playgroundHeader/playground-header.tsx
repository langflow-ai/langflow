import { useShallow } from "zustand/react/shallow";
import { DEFAULT_SESSION_NAME } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { HeaderButton } from "./components/header-button";
import { SessionManagerPopover } from "./components/session-manager-popover";
import { useAddNewSession } from "./hooks/useAddNewSession";

export function PlaygroundHeader({ onClose }: { onClose?: () => void }) {
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));

  const addSession = useAddNewSession();

  const sessionName =
    selectedSession === flowId ? DEFAULT_SESSION_NAME : selectedSession;

  return (
    <div className="flex items-center justify-between gap-2 px-4 py-2">
      <div className="flex items-center gap-2">
        <div className="truncate text-sm font-medium text-secondary-foreground">
          {sessionName}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <HeaderButton icon="Plus" onClick={addSession} />
        <SessionManagerPopover>
          <HeaderButton icon="History" />
        </SessionManagerPopover>
        <HeaderButton icon="ExternalLink" onClick={() => {}} />
        <HeaderButton icon="MoreHorizontal" onClick={() => {}} />
        {onClose && <HeaderButton icon="X" onClick={onClose} />}
      </div>
    </div>
  );
}
