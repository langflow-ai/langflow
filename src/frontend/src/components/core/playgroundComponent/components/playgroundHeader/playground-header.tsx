import { useShallow } from "zustand/react/shallow";
import { DEFAULT_SESSION_NAME } from "@/constants/constants";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { HeaderButton } from "./components/header-button";
import { SessionManagerDropdown } from "./components/session-manager-dropdown";

export function PlaygroundHeader() {
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));

  const sessionName =
    selectedSession === flowId ? DEFAULT_SESSION_NAME : selectedSession;

  return (
    <div className="flex items-center justify-between gap-2 px-4 py-3">
      <div className="flex items-center gap-2">
        <SessionManagerDropdown>
          <HeaderButton icon="ListRestart" />
        </SessionManagerDropdown>
        <div className="truncate text-sm font-medium text-secondary-foreground">
          {sessionName}
        </div>
      </div>
      <div className="flex items-center gap-1">
        <HeaderButton icon="MoreVertical" onClick={() => {}} />
        <HeaderButton icon="Expand" onClick={() => {}} />
      </div>
    </div>
  );
}
