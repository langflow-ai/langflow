import { useEffect, useMemo, useRef, useState } from "react";
import useFlowStore from "../../stores/flowStore";
import { ChatType } from "../../types/chat";
import IOView from "../IOview";
import ChatTrigger from "../ViewTriggers/chat";
import { Transition } from "@headlessui/react";
import ForwardedIconComponent from "../genericIconComponent";
import { Separator } from "../ui/separator";
import ShareModal from "../../modals/shareModal";
import { useStoreStore } from "../../stores/storeStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { classNames } from "../../utils/utils";
import ApiModal from "../../modals/ApiModal";

export default function Chat({ flow }: ChatType): JSX.Element {
  const [open, setOpen] = useState(false);
  const flowState = useFlowStore((state) => state.flowState);
  const nodes = useFlowStore((state) => state.nodes);
  const hasIO = useFlowStore((state) => state.hasIO);
  const hasStore = useStoreStore((state) => state.hasStore);
  const validApiKey = useStoreStore((state) => state.validApiKey);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const hasApiKey = useStoreStore((state) => state.hasApiKey);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        (event.key === "K" || event.key === "k") &&
        (event.metaKey || event.ctrlKey) &&
        useFlowStore.getState().hasIO
      ) {
        event.preventDefault();
        setOpen((oldState) => !oldState);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const prevNodesRef = useRef<any[] | undefined>();

  const ModalMemo = useMemo(
    () => (
      <ShareModal
        is_component={false}
        component={currentFlow!}
        disabled={!hasApiKey || !validApiKey || !hasStore}
      >
        <button
          disabled={!hasApiKey || !validApiKey || !hasStore}
          className={classNames(
            "relative inline-flex w-full h-full items-center justify-center hover:bg-hover bg-muted hover:bg-background px-5 py-3 text-foreground transition-all duration-500 ease-in-out gap-[4px] text-sm font-semibold",
            !hasApiKey || !validApiKey || !hasStore
              ? "button-disable  cursor-default text-muted-foreground"
              : ""
          )}
        >
          <ForwardedIconComponent
            name="Share3"
            className={classNames(
              "-m-0.5 -ml-1 h-6 w-6",
              !hasApiKey || !validApiKey || !hasStore
                ? "extra-side-bar-save-disable"
                : ""
            )}
          />
          Share
        </button>
      </ShareModal>
    ),
    [hasApiKey, validApiKey, currentFlow, hasStore]
  );

  return (
    <>
      <Transition
      show={true}
      appear={true}
      enter="transition ease-out duration-300"
      enterFrom="translate-y-96"
      enterTo="translate-y-0"
      leave="transition ease-in duration-300"
      leaveFrom="translate-y-0"
      leaveTo="translate-y-96"
      >
      <div
        className={
          "shadow-round-btn-shadow hover:shadow-round-btn-shadow message-button-position flex items-center justify-center rounded-sm bg-muted  shadow-md transition-all cursor-pointer gap-7 border"
        }
      >
        <div className="flex">
          <div className="flex gap-1 text-medium-indigo  rounded-sm transition-all w-full h-full">
          {hasIO && (
          <IOView open={open} setOpen={setOpen}>
            <div className="relative inline-flex w-full items-center justify-center   hover:bg-hover transition-all duration-500 ease-in-out px-5 py-3 text-medium-indigo ease-in-out gap-1 text-sm font-semibold">
              <ForwardedIconComponent
                name="Zap"
                className={"message-button-icon h-5 w-5 transition-all"}
              />
              Run
            </div>
          </IOView>
        )}
          </div>
          {hasIO && (
            <div>
              <Separator orientation="vertical" />
            </div>
          )}
          <div className="flex items-center gap-2">
            {currentFlow && currentFlow.data && (
              <ApiModal flow={currentFlow}>
                  <div className={classNames("relative inline-flex w-full items-center justify-center hover:bg-hover px-5 py-3 text-foreground transition-all duration-500 ease-in-out gap-1 text-sm font-semibold")}>
                    <ForwardedIconComponent
                      name="Code2"
                      className={" h-5 w-5"}
                    />
                    API
                  </div>
              </ApiModal>
            )}
          </div>
          {hasStore && validApiKey && (
            <div>
              <Separator orientation="vertical" />
            </div>
          )}
          <div className="flex items-center gap-2">
            {hasStore && validApiKey && (
              <div className="side-bar-button">{ModalMemo}</div>
            )}
          </div>
        </div>
      </div>
    </Transition>
    </>
  );
}
