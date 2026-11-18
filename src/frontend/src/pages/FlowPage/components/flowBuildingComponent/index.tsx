import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { normalizeTimeString } from "@/CustomNodes/GenericNode/components/NodeStatus/utils/format-run-time";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { BorderTrail } from "@/components/core/border-trail";
import { Button } from "@/components/ui/button";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { BuildStatus } from "@/constants/enums";
import useFlowStore from "@/stores/flowStore";
import type { FlowStoreType } from "@/types/zustand/flow";
import { cn } from "@/utils/utils";
import { getRunningNodeLabel } from "./helpers/get-running-node-label";
import {
  CONTAINER_VARIANTS,
  DISMISS_BUTTON_VARIANTS,
  getTimeVariants,
  RETRY_BUTTON_VARIANTS,
  STOP_BUTTON_VARIANTS,
} from "./helpers/visual-variants";

type BuildInfo = FlowStoreType["buildInfo"];

const AUTO_DISMISS_MS = 2000;
const EXIT_ANIMATION_MS = 500;

export default function FlowBuildingComponent() {
  const { t } = useTranslation();
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const flowBuildStatus = useFlowStore((state) => state.flowBuildStatus);
  const buildInfo = useFlowStore((state) => state.buildInfo);
  const errorButtonsRef = useRef<HTMLDivElement>(null);
  const stopButtonRef = useRef<HTMLDivElement>(null);
  const setBuildInfo = useFlowStore((state) => state.setBuildInfo);
  const [duration, setDuration] = useState(0);
  // The result the user (or the auto-dismiss timer) dismissed.
  // A newer result is a new object, so an old dismissal never hides it.
  const [dismissedInfo, setDismissedInfo] = useState<BuildInfo>(null);
  const dismissed = buildInfo !== null && buildInfo === dismissedInfo;
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const prevIsBuilding = useRef(isBuilding);
  const startTimeRef = useRef<number | null>(null);
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
      setDuration(0);
      startTimeRef.current = Date.now();
    }

    if (isBuilding && startTimeRef.current !== null) {
      intervalId = setInterval(() => {
        setDuration(Date.now() - startTimeRef.current!);
      }, 10);
    }

    if (!isBuilding && prevIsBuilding.current) {
      startTimeRef.current = null;
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
          ? t("flowBuild.runningNode", {
              id: getRunningNodeLabel(statusBuilding[0]?.id),
            })
          : t("flowBuild.runningFlow")}
      </TextShimmer>
    );
  }, [isBuilding, statusBuilding]);

  // Dismiss a successful result after a short delay.
  // The cleanup cancels the timer when a newer result replaces this one.
  useEffect(() => {
    if (!buildInfo?.success) return;
    const timer = setTimeout(
      () => setDismissedInfo(buildInfo),
      AUTO_DISMISS_MS,
    );
    return () => clearTimeout(timer);
  }, [buildInfo]);

  // Clear buildInfo after the exit animation, only while this result is still dismissed.
  useEffect(() => {
    if (!dismissed) return;
    const timer = setTimeout(() => setBuildInfo(null), EXIT_ANIMATION_MS);
    return () => clearTimeout(timer);
  }, [dismissed, setBuildInfo]);

  // Mark the current result as dismissed. The effect above clears it.
  const handleDismiss = () => {
    setDismissedInfo(buildInfo);
  };

  // Show the panel while building, or while there is an undismissed result.
  const hasResult = Boolean(buildInfo?.error || buildInfo?.success);
  const showPanel = isBuilding || (hasResult && !dismissed);

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
      {showPanel && (
        <div className="absolute bottom-16 left-1/2 z-50 w-[530px] -translate-x-1/2">
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
                          t("flowBuild.builtSuccessfully")
                        ) : (
                          <div className="flex items-center gap-2">
                            <ForwardedIconComponent
                              name="CircleAlert"
                              className="h-5 w-5"
                            />
                            {t("flowBuild.buildFailed")}
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
                                    {t("flowBuild.retry")}
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
                                    {t("flowBuild.dismiss")}
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
                                  {t("flowBuild.stop")}
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
                        role="region"
                        aria-label={t("flowBuild.buildFailed")}
                        tabIndex={0}
                        className="max-h-48 overflow-y-auto"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        <Markdown
                          remarkPlugins={[remarkGfm]}
                          className="my-1.5 break-words [&>p+p]:mt-2"
                          components={{
                            a: ({ node, ...props }) => (
                              <a
                                {...props}
                                target="_blank"
                                className="underline"
                                rel="noopener noreferrer"
                              >
                                {props.children}
                              </a>
                            ),
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
