import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { normalizeTimeString } from "@/CustomNodes/GenericNode/components/NodeStatus/utils/format-run-time";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { BorderTrail } from "@/components/core/border-trail";
import { Button } from "@/components/ui/button";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { BuildStatus } from "@/constants/enums";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import {
  CONTAINER_VARIANTS,
  DISMISS_BUTTON_VARIANTS,
  getTimeVariants,
  RETRY_BUTTON_VARIANTS,
  STOP_BUTTON_VARIANTS,
} from "./helpers/visual-variants";

export default function FlowBuildingComponent() {
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const flowBuildStatus = useFlowStore((state) => state.flowBuildStatus);
  const buildInfo = useFlowStore((state) => state.buildInfo);
  const errorButtonsRef = useRef<HTMLDivElement>(null);
  const stopButtonRef = useRef<HTMLDivElement>(null);
  const setBuildInfo = useFlowStore((state) => state.setBuildInfo);
  const [duration, setDuration] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const prevIsBuilding = useRef(isBuilding);
  const pastBuildFlowParams = useFlowStore(
    (state) => state.pastBuildFlowParams,
  );
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const statusBuilding = useMemo(
    () =>
      Object.entries(flowBuildStatus)
        .filter(([_, s]) => s.status === BuildStatus.BUILDING)
        .map(([id, s]) => ({
          id,
          ...s,
        })),
    [flowBuildStatus],
  );

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (isBuilding && !prevIsBuilding.current) {
      setDismissed(false);
      setDuration(0);
    }

    if (isBuilding) {
      intervalId = setInterval(() => {
        setDuration((prev) => prev + 10);
      }, 10);
    }

    prevIsBuilding.current = isBuilding;

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [isBuilding]);

  const displayTime = duration ?? 0;
  const secondsValue = displayTime / 1000;
  const humanizedTime =
    normalizeTimeString(`${secondsValue.toFixed(1)}seconds`) ??
    `${secondsValue.toFixed(1)}s`;

  const buildingContent = useMemo(() => {
    if (!isBuilding) return null;
    return (
      <TextShimmer duration={1}>
        {statusBuilding.length > 0
          ? `Running ${statusBuilding[0]?.id}`
          : "Running flow"}
      </TextShimmer>
    );
  }, [isBuilding, statusBuilding]);

  useEffect(() => {
    if (buildInfo?.success) {
      setTimeout(() => {
        handleDismiss();
      }, 2000);
    }
  }, [buildInfo?.success]);

  const handleDismiss = () => {
    setDismissed(true);
    setTimeout(() => {
      setBuildInfo(null);
      setDismissed(false);
    }, 500);
  };

  const handleStop = () => {
    stopBuilding();
  };

  const handleRetry = () => {
    if (pastBuildFlowParams) {
      buildFlow(pastBuildFlowParams);
    }
  };

  return (
    <AnimatePresence mode="wait">
      {(isBuilding || buildInfo?.error || buildInfo?.success) && !dismissed && (
        <div className="absolute bottom-2 left-1/2 z-50 w-[530px] -translate-x-1/2">
          <motion.div
            initial="hidden"
            animate="visible"
            exit="exit"
            variants={CONTAINER_VARIANTS}
            transition={{ duration: 0.2, delay: 0.2, ease: "easeOut" }}
            className={cn(
              "flex flex-col justify-center overflow-hidden rounded-lg border bg-background px-4 py-2 text-sm shadow-md transition-colors duration-200",
              !isBuilding &&
                buildInfo?.error &&
                "border-accent-red-foreground text-accent-red-foreground",
              !isBuilding &&
                buildInfo?.success &&
                "border-accent-emerald-foreground text-accent-emerald-foreground",
            )}
          >
            <AnimatePresence mode="wait">
              {(isBuilding || buildInfo?.error || buildInfo?.success) && (
                <>
                  {isBuilding && (
                    <BorderTrail
                      size={100}
                      transition={{
                        repeat: Infinity,
                        duration: 10,
                        ease: "linear",
                      }}
                    />
                  )}
                  <div className="flex min-h-10 w-full items-center justify-between gap-2">
                    <AnimatePresence mode="wait">
                      <div>
                        {buildingContent ? (
                          buildingContent
                        ) : buildInfo?.success ? (
                          "Flow built successfully"
                        ) : (
                          <div className="flex items-center gap-2">
                            <ForwardedIconComponent
                              name="CircleAlert"
                              className="h-5 w-5"
                            />
                            Flow build failed
                          </div>
                        )}
                      </div>
                    </AnimatePresence>
                    <div className="relative flex items-center gap-4">
                      <motion.div
                        variants={getTimeVariants(
                          buildInfo?.error ? errorButtonsRef : stopButtonRef,
                        )}
                        animate={!buildInfo?.success ? "double" : "single"}
                        transition={{
                          duration: 0.2,
                          ease: "easeOut",
                        }}
                        className="absolute right-0 font-mono text-xs"
                      >
                        {humanizedTime}
                      </motion.div>
                      <AnimatePresence mode="sync">
                        {!buildInfo?.success && (
                          <div className="absolute right-0">
                            {buildInfo?.error ? (
                              <motion.div
                                key="error-buttons"
                                ref={errorButtonsRef}
                                className="flex items-center gap-2"
                              >
                                <motion.div
                                  variants={RETRY_BUTTON_VARIANTS}
                                  initial="hidden"
                                  animate="visible"
                                  exit="exit"
                                  transition={{ duration: 0.2 }}
                                >
                                  <Button size="sm" onClick={handleRetry}>
                                    Retry
                                  </Button>
                                </motion.div>
                                <motion.div
                                  variants={DISMISS_BUTTON_VARIANTS}
                                  initial="hidden"
                                  animate="visible"
                                  exit="exit"
                                  transition={{ duration: 0.2 }}
                                >
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="text-primary"
                                    onClick={handleDismiss}
                                  >
                                    Dismiss
                                  </Button>
                                </motion.div>
                              </motion.div>
                            ) : (
                              <motion.div
                                key="stop-button"
                                variants={STOP_BUTTON_VARIANTS}
                                ref={stopButtonRef}
                                initial="hidden"
                                animate="visible"
                                className=""
                                exit="exit"
                                transition={{ duration: 0.2 }}
                              >
                                <Button
                                  data-testid="stop_building_button"
                                  size="sm"
                                  onClick={handleStop}
                                >
                                  Stop
                                </Button>
                              </motion.div>
                            )}
                          </div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>
                  <AnimatePresence>
                    {buildInfo?.error && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        <Markdown
                          linkTarget="_blank"
                          remarkPlugins={[remarkGfm]}
                          className="my-1.5 align-text-top truncate-doubleline"
                          components={{
                            a: ({ node, ...props }) => (
                              <a
                                href={props.href}
                                target="_blank"
                                className="underline"
                                rel="noopener noreferrer"
                              >
                                {props.children}
                              </a>
                            ),
                            p({ node, ...props }) {
                              return (
                                <span className="inline-block w-fit max-w-full align-text-top truncate-doubleline">
                                  {props.children}
                                </span>
                              );
                            },
                          }}
                        >
                          {buildInfo?.error?.join("\n")}
                        </Markdown>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
