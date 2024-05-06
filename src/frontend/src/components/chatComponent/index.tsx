import { Transition } from "@headlessui/react";
import { useEffect, useMemo, useRef, useState } from "react";
import IOModal from "../../modals/IOModal";
import ApiModal from "../../modals/apiModal";
import ShareModal from "../../modals/shareModal";
import useFlowStore from "../../stores/flowStore";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { useStoreStore } from "../../stores/storeStore";
import { classNames } from "../../utils/utils";
import ForwardedIconComponent from "../genericIconComponent";
import { Separator } from "../ui/separator";

export default function FlowToolbar(): JSX.Element {
  const [open, setOpen] = useState(false);
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
            "relative inline-flex h-full w-full items-center justify-center gap-[4px] bg-muted px-5 py-3 text-sm font-semibold text-foreground transition-all duration-150 ease-in-out hover:bg-background hover:bg-hover ",
            !hasApiKey || !validApiKey || !hasStore
              ? " button-disable text-muted-foreground  "
              : "",
          )}
        >
          <ForwardedIconComponent
            name="Share3"
            className={classNames(
              "-m-0.5 -ml-1 h-6 w-6",
              !hasApiKey || !validApiKey || !hasStore
                ? "extra-side-bar-save-disable"
                : "",
            )}
          />
          Share
        </button>
      </ShareModal>
    ),
    [hasApiKey, validApiKey, currentFlow, hasStore],
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
            "shadow-round-btn-shadow hover:shadow-round-btn-shadow message-button-position flex items-center justify-center gap-7 rounded-sm  border bg-muted shadow-md transition-all"
          }
        >
          <div className="flex">
            <div className="flex h-full w-full  gap-1 rounded-sm transition-all">
              {hasIO ? (
                <IOModal open={open} setOpen={setOpen} disable={!hasIO}>
                  <div className="relative inline-flex w-full items-center justify-center   gap-1 px-5 py-3 text-sm font-semibold transition-all duration-500 ease-in-out hover:bg-hover">
                    <ForwardedIconComponent
                      name="BotMessageSquareIcon"
                      className={" h-5 w-5 transition-all"}
                    />
                    Playground
                  </div>
                </IOModal>
              ) : (
                <div
                  className={`relative inline-flex w-full cursor-not-allowed items-center justify-center gap-1 px-5 py-3 text-sm font-semibold text-muted-foreground transition-all duration-150 ease-in-out ease-in-out`}
                >
                  <ForwardedIconComponent
                    name="BotMessageSquareIcon"
                    className={" h-5 w-5 transition-all"}
                  />
                  Playground
                </div>
              )}
            </div>
            <div>
              <Separator orientation="vertical" />
            </div>
            <div className="flex cursor-pointer items-center gap-2">
              {currentFlow && currentFlow.data && (
                <ApiModal flow={currentFlow}>
                  <div
                    className={classNames(
                      "relative inline-flex w-full items-center justify-center gap-1 px-5 py-3 text-sm font-semibold text-foreground transition-all duration-150 ease-in-out hover:bg-hover",
                    )}
                  >
                    <ForwardedIconComponent
                      name="Code2"
                      className={" h-5 w-5"}
                    />
                    API
                  </div>
                </ApiModal>
              )}
            </div>
            <div>
              <Separator orientation="vertical" />
            </div>
            <div className="flex items-center gap-2">
              <div
                className={`side-bar-button ${
                  !hasApiKey || !validApiKey || !hasStore
                    ? " cursor-not-allowed"
                    : " cursor-pointer"
                }`}
              >
                {ModalMemo}
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </>
  );
}
