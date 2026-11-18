import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
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
  RETRY_BUTTON_VARIANTS,
  STOP_BUTTON_VARIANTS,
} from "./helpers/visual-variants";

type BuildInfo = FlowStoreType["buildInfo"];

const AUTO_DISMISS_MS = 2000;
const EXIT_ANIMATION_MS = 500;
// The time label shows tenths of a second.
const TICK_MS = 100;

export default function FlowBuildingComponent() {
  const { t } = useTranslation();
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const flowBuildStatus = useFlowStore((state) => state.flowBuildStatus);
  const buildInfo = useFlowStore((state) => state.buildInfo);
  const setBuildInfo = useFlowStore((state) => state.setBuildInfo);
  const [duration, setDuration] = useState(0);
  // The result the user (or the auto-dismiss timer) dismissed.
  // A newer result is a new object, so an old dismissal never hides it.
  const [dismissedInfo, setDismissedInfo] = useState<BuildInfo>(null);
  const dismissed = buildInfo !== null && buildInfo === dismissedInfo;
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const pastBuildFlowParams = useFlowStore(
    (state) => state.pastBuildFlowParams,
  );
  const buildFlow = useFlowStore((state) => state.buildFlow);
  // The id of the first node that is building, if any.
  const runningNodeId = useMemo(
    () =>
      Object.entries(flowBuildStatus).find(
        ([, s]) => s.status === BuildStatus.BUILDING,
      )?.[0],
    [flowBuildStatus],
  );

  // Count the build time. Start when a build runs, also when the component mounts mid-build.
  // The last value stays in state, so the result still shows it.
  useEffect(() => {
    if (!isBuilding) return;
    const start = Date.now();
    setDuration(0);
    const timer = setInterval(() => setDuration(Date.now() - start), TICK_MS);
    return () => clearInterval(timer);
  }, [isBuilding]);

  const secondsValue = duration / 1000;
  const humanizedTime =
    normalizeTimeString(`${secondsValue.toFixed(1)}seconds`) ??
    `${secondsValue.toFixed(1)}s`;

  // The text shown while a build runs.
  const buildingContent = isBuilding ? (
    <TextShimmer duration={1}>
      {runningNodeId
        ? t("flowBuild.runningNode", { id: getRunningNodeLabel(runningNodeId) })
        : t("flowBuild.runningFlow")}
    </TextShimmer>
  ) : null;

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

  // Clear the dismissed result after the exit animation.
  // On unmount, clear it at once so the store does not keep a hidden result.
  // The guard skips the clear when a newer result replaced this one.
  useEffect(() => {
    if (!dismissed) return;
    const dismissedResult = buildInfo;
    const clearIfStillDismissed = () => {
      if (useFlowStore.getState().buildInfo === dismissedResult)
        setBuildInfo(null);
    };
    const timer = setTimeout(clearIfStillDismissed, EXIT_ANIMATION_MS);
    return () => {
      clearTimeout(timer);
      clearIfStillDismissed();
    };
  }, [dismissed, buildInfo, setBuildInfo]);

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
              <div className="flex items-center gap-4">
                <motion.div
                  layout
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  className="font-mono text-xs"
                >
                  {humanizedTime}
                </motion.div>
                {/* popLayout takes the exiting buttons out of the flex flow, so the time label slides instead of jumping. */}
                <AnimatePresence mode="popLayout">
                  {!buildInfo?.success &&
                    (buildInfo?.error ? (
                      <motion.div
                        key="error-buttons"
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
                        initial="hidden"
                        animate="visible"
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
                    ))}
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
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
