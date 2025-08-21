import { Panel } from "@xyflow/react";
import { memo, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useShortcutsStore } from "../../../stores/shortcuts";
import { cn, isThereModal } from "../../../utils/utils";
import FlowToolbarOptions from "./components/flow-toolbar-options";

const FlowToolbar = memo(function FlowToolbar(): JSX.Element {
  const preventDefault = true;
  const [openCodeModal, setOpenCodeModal] = useState<boolean>(false);
  const [openShareModal, setOpenShareModal] = useState<boolean>(false);
  function handleAPIWShortcut(e: KeyboardEvent) {
    if (isThereModal() && !openCodeModal) return;
    setOpenCodeModal((oldOpen) => !oldOpen);
  }

  function handleShareWShortcut(e: KeyboardEvent) {
    if (isThereModal() && !openShareModal) return;
    setOpenShareModal((oldState) => !oldState);
  }

  const api = useShortcutsStore((state) => state.api);
  const flow = useShortcutsStore((state) => state.flow);

  useHotkeys(api, handleAPIWShortcut, { preventDefault });
  useHotkeys(flow, handleShareWShortcut, { preventDefault });

  return (
    <Panel className="!top-auto !m-2" position="top-right">
      <div
        className={cn(
          "hover:shadow-round-btn-shadow flex items-center justify-center gap-7 rounded-lg border bg-background p-1 shadow transition-all",
        )}
      >
        <FlowToolbarOptions />
      </div>
    </Panel>
  );
});

export default FlowToolbar;
