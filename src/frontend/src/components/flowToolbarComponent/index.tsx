import ShadTooltip from "@/components/shadTooltipComponent";
import { ENABLE_API } from "@/customization/feature-flags";
import { track } from "@/customization/utils/analytics";
import IOModal from "@/modals/IOModal/newModal";
import { useEffect, useMemo, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { Panel } from "reactflow";
import ApiModal from "../../modals/apiModal";
import ShareModal from "../../modals/shareModal";
import useFlowStore from "../../stores/flowStore";
import { useShortcutsStore } from "../../stores/shortcuts";
import { useStoreStore } from "../../stores/storeStore";
import { classNames, isThereModal } from "../../utils/utils";
import ForwardedIconComponent from "../genericIconComponent";

export default function FlowToolbar(): JSX.Element {
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

  const openPlayground = useShortcutsStore((state) => state.open);
  const api = useShortcutsStore((state) => state.api);
  const flow = useShortcutsStore((state) => state.flow);

  useHotkeys(openPlayground, handleChatWShortcut, { preventDefault });
  useHotkeys(api, handleAPIWShortcut, { preventDefault });
  useHotkeys(flow, handleShareWShortcut, { preventDefault });

  const hasIO = useFlowStore((state) => state.hasIO);
  const hasStore = useStoreStore((state) => state.hasStore);
  const validApiKey = useStoreStore((state) => state.validApiKey);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);
  const currentFlow = useFlowStore((state) => state.currentFlow);

  useEffect(() => {
    if (open) {
      track("Playground Button Clicked");
    }
  }, [open]);

  const ModalMemo = useMemo(
    () => (
      <ShareModal
        is_component={false}
        component={currentFlow!}
        disabled={!hasApiKey || !validApiKey || !hasStore}
        open={openShareModal}
        setOpen={setOpenShareModal}
      >
        <ShadTooltip
          content={
            !hasApiKey || !validApiKey || !hasStore
              ? "Store API Key Required"
              : ""
          }
          side="bottom"
          align="end"
        >
          <button
            disabled={!hasApiKey || !validApiKey || !hasStore}
            className={classNames(
              "relative inline-flex h-8 w-full items-center justify-center gap-1.5 rounded px-3 py-1.5 text-sm font-semibold text-foreground transition-all duration-150 ease-in-out",
              !hasApiKey || !validApiKey || !hasStore
                ? "cursor-not-allowed text-muted-foreground"
                : "hover:bg-accent",
            )}
            data-testid="shared-button-flow"
            onClick={() => {
              setOpenShareModal(true);
            }}
          >
            <>
              <ForwardedIconComponent
                name="Share2"
                className={classNames(
                  "h-4 w-4",
                  !hasApiKey || !validApiKey || !hasStore
                    ? "extra-side-bar-save-disable"
                    : "",
                )}
              />
              <span className="hidden md:block">Share</span>
            </>
          </button>
        </ShadTooltip>
      </ShareModal>
    ),
    [
      hasApiKey,
      validApiKey,
      currentFlow,
      hasStore,
      openShareModal,
      setOpenShareModal,
    ],
  );

  return (
    <>
      <Panel className="!m-2" position="top-right">
        <div
          className={
            "hover:shadow-round-btn-shadow flex items-center justify-center gap-7 rounded-md border bg-background p-1.5 shadow transition-all"
          }
        >
          <div className="flex gap-1.5">
            <div className="flex h-full w-full gap-1.5 rounded-sm transition-all">
              {hasIO ? (
                <IOModal
                  open={open}
                  setOpen={setOpen}
                  disable={!hasIO}
                  canvasOpen
                >
                  <div
                    data-testid="playground-btn-flow-io"
                    className="relative inline-flex h-8 w-full items-center justify-center gap-1.5 rounded px-3 py-1.5 text-sm font-semibold transition-all duration-500 ease-in-out hover:bg-accent"
                  >
                    <ForwardedIconComponent
                      name="Play"
                      className={"h-4 w-4 transition-all"}
                    />
                    <span className="hidden md:block">Playground</span>
                  </div>
                </IOModal>
              ) : (
                <ShadTooltip content="Add a Chat Input or Chat Output to use the playground">
                  <div
                    className={`relative inline-flex h-8 w-full cursor-not-allowed items-center justify-center gap-1 px-5 py-3 text-sm font-semibold text-muted-foreground transition-all duration-150 ease-in-out`}
                    data-testid="playground-btn-flow"
                  >
                    <ForwardedIconComponent
                      name="BotMessageSquareIcon"
                      className={"h-5 w-5 transition-all"}
                    />
                    <span className="hidden md:block">Playground</span>
                  </div>
                </ShadTooltip>
              )}
            </div>
            {ENABLE_API && (
              <>
                <div className="flex cursor-pointer items-center gap-2">
                  {currentFlow && currentFlow.data && (
                    <ApiModal
                      flow={currentFlow}
                      open={openCodeModal}
                      setOpen={setOpenCodeModal}
                    >
                      <div
                        className={classNames(
                          "relative inline-flex h-8 w-full items-center justify-center gap-1.5 rounded px-3 py-1.5 text-sm font-semibold text-foreground transition-all duration-150 ease-in-out hover:bg-accent",
                        )}
                      >
                        <ForwardedIconComponent
                          name="Code2"
                          className={"h-4 w-4"}
                        />
                        <span className="hidden md:block">API</span>
                      </div>
                    </ApiModal>
                  )}
                </div>
              </>
            )}
            <div className="flex items-center gap-2">
              <div
                className={`side-bar-button ${
                  !hasApiKey || !validApiKey || !hasStore
                    ? "cursor-not-allowed"
                    : "cursor-pointer"
                }`}
              >
                {ModalMemo}
              </div>
            </div>
          </div>
        </div>
      </Panel>
    </>
  );
}
