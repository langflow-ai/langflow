import { Panel } from "@xyflow/react";
import { memo, useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { track } from "@/customization/utils/analytics";
import ExportModal from "@/modals/exportModal";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import useFlowStore from "../../../stores/flowStore";
import { useShortcutsStore } from "../../../stores/shortcuts";
import { cn, isThereModal } from "../../../utils/utils";
import FlowToolbarOptions from "./components/flow-toolbar-options";

const FlowToolbar = memo(function FlowToolbar(): JSX.Element {
  const preventDefault = true;
  const [openApiModal, setOpenApiModal] = useState<boolean>(false);
  const [openExportModal, setOpenExportModal] = useState<boolean>(false);
  const isPlaygroundOpen = usePlaygroundStore((state) => state.isOpen);
  const setPlaygroundOpen = usePlaygroundStore((state) => state.setIsOpen);
  const handleAPIWShortcut = (e: KeyboardEvent) => {
    if (isThereModal() && !openApiModal) return;
    setOpenApiModal((oldOpen) => !oldOpen);
  };

  const handleChatWShortcut = (e: KeyboardEvent) => {
    if (isThereModal() && !isPlaygroundOpen) return;
    if (useFlowStore.getState().hasIO) {
      setPlaygroundOpen(!isPlaygroundOpen);
    }
  };

  const handleShareWShortcut = (e: KeyboardEvent) => {
    if (isThereModal() && !openExportModal) return;
    setOpenExportModal((oldState) => !oldState);
  };

  const openPlayground = useShortcutsStore((state) => state.openPlayground);
  const api = useShortcutsStore((state) => state.api);
  const flow = useShortcutsStore((state) => state.flow);

  useHotkeys(openPlayground, handleChatWShortcut, { preventDefault });
  useHotkeys(api, handleAPIWShortcut, { preventDefault });
  useHotkeys(flow, handleShareWShortcut, { preventDefault });

  useEffect(() => {
    if (isPlaygroundOpen) {
      track("Playground Button Clicked");
    }
  }, [isPlaygroundOpen]);

  return (
    <>
      <Panel className="!top-auto !m-2" position="top-right">
        <div
          className={cn(
            "hover:shadow-round-btn-shadow flex h-11 items-center justify-center gap-7 rounded-md border bg-background px-1.5 shadow transition-all",
          )}
        >
          <FlowToolbarOptions
            openApiModal={openApiModal}
            setOpenApiModal={setOpenApiModal}
          />
        </div>
      </Panel>
      <ExportModal open={openExportModal} setOpen={setOpenExportModal} />
    </>
  );
});

export default FlowToolbar;
