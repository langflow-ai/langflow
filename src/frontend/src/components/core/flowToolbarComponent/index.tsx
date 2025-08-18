import { Panel } from "@xyflow/react";
import { memo, useEffect, useMemo, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { track } from "@/customization/utils/analytics";
import ShareModal from "../../../modals/shareModal";
import useFlowStore from "../../../stores/flowStore";
import { useShortcutsStore } from "../../../stores/shortcuts";
import { useStoreStore } from "../../../stores/storeStore";
import { classNames, cn, isThereModal } from "../../../utils/utils";
import ForwardedIconComponent from "../../common/genericIconComponent";
import FlowToolbarOptions from "./components/flow-toolbar-options";

const FlowToolbar = memo(function FlowToolbar(): JSX.Element {
  const preventDefault = true;
  const [open, setOpen] = useState<boolean>(false);
  const [openCodeModal, setOpenCodeModal] = useState<boolean>(false);
  const [openShareModal, setOpenShareModal] = useState<boolean>(false);
  function handleAPIWShortcut(e: KeyboardEvent) {
    if (isThereModal() && !openCodeModal) return;
    setOpenCodeModal((oldOpen) => !oldOpen);
  }

  function handleChatWShortcut(e: KeyboardEvent) {
    if (isThereModal() && !open) return;
    if (useFlowStore.getState().hasIO) {
      setOpen((oldState) => !oldState);
    }
  }

  function handleShareWShortcut(e: KeyboardEvent) {
    if (isThereModal() && !openShareModal) return;
    setOpenShareModal((oldState) => !oldState);
  }

  const openPlayground = useShortcutsStore((state) => state.openPlayground);
  const api = useShortcutsStore((state) => state.api);
  const flow = useShortcutsStore((state) => state.flow);

  useHotkeys(openPlayground, handleChatWShortcut, { preventDefault });
  useHotkeys(api, handleAPIWShortcut, { preventDefault });
  useHotkeys(flow, handleShareWShortcut, { preventDefault });

  useEffect(() => {
    if (open) {
      track("Playground Button Clicked");
    }
  }, [open]);

  return (
    <>
      <Panel className="!top-auto !m-2" position="top-right">
        <div
          className={cn(
            "hover:shadow-round-btn-shadow flex h-11 items-center justify-center gap-7 rounded-md border bg-background px-1.5 shadow transition-all",
          )}
        >
          <FlowToolbarOptions />
        </div>
      </Panel>
    </>
  );
});

export default FlowToolbar;
