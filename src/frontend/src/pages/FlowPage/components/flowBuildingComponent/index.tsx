import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { BorderTrail } from "@/components/core/border-trail";
import { Button } from "@/components/ui/button";
import { TextShimmer } from "@/components/ui/TextShimmer";
import { BuildStatus } from "@/constants/enums";
import { normalizeTimeString } from "@/CustomNodes/GenericNode/components/NodeStatus/utils/format-run-time";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
export default function FlowBuildingComponent() {
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const flowBuildStatus = useFlowStore((state) => state.flowBuildStatus);
  const [error, setError] = useState<string | undefined>(undefined);
  const [duration, setDuration] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const prevIsBuilding = useRef(isBuilding);
  const pastBuildFlowParams = useFlowStore(
    (state) => state.pastBuildFlowParams,
  );
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const statusError = useMemo(
    () =>
      Object.entries(flowBuildStatus)
        .filter(([_, s]) => s.status === BuildStatus.ERROR)
        .map(([id, s]) => ({
          id,
          ...s,
        })),
    [flowBuildStatus],
  );
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
    if (statusError.length > 0) {
      setError(statusError[0].error?.join("\n") ?? undefined);
    }
  }, [flowBuildStatus]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    if (isBuilding && !prevIsBuilding.current) {
      setDismissed(false);
      setError(undefined);
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

  const handleDismiss = () => {
    setDismissed(true);
    setTimeout(() => {
      setError(undefined);
    }, 1000);
  };

  const handleStop = () => {
    stopBuilding();
  };

  const handleRetry = () => {
    setError(undefined);
    if (pastBuildFlowParams) {
      buildFlow(pastBuildFlowParams);
    }
  };

  return (
    <div
      className={cn(
        "absolute bottom-2 left-1/2 z-50 flex w-[530px] -translate-x-1/2 flex-col items-center justify-between gap-4 rounded-lg border bg-background px-4 py-2 text-sm shadow-md transition-all ease-out",
        ((!isBuilding && statusError.length === 0) || dismissed) &&
          "bottom-0 translate-y-[120%]",
        !isBuilding &&
          statusError.length > 0 &&
          "border-accent-red-foreground text-accent-red-foreground",
      )}
    >
      <AnimatePresence>
        {(isBuilding || statusError.length > 0) && (
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
            <div className="flex w-full items-center justify-between gap-2">
              {buildingContent || (
                <span className="flex items-center gap-2">
                  <ForwardedIconComponent
                    name="CircleAlert"
                    className="h-5 w-5"
                  />
                  Flow build failed
                </span>
              )}
              <div className="flex items-center gap-2">
                <span className="mr-2 font-mono text-xs">{humanizedTime}</span>
                {error ? (
                  <>
                    <Button size="sm" onClick={handleRetry}>
                      Retry
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-primary"
                      onClick={handleDismiss}
                    >
                      Dismiss
                    </Button>
                  </>
                ) : (
                  <Button size="sm" onClick={handleStop}>
                    Stop
                  </Button>
                )}
              </div>
            </div>
            {error && (
              <div className="flex items-center">
                <Markdown
                  linkTarget="_blank"
                  remarkPlugins={[remarkGfm]}
                  className="align-text-top truncate-doubleline"
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
                        <span className="inline-block w-fit max-w-full align-text-top">
                          {props.children}
                        </span>
                      );
                    },
                  }}
                >
                  {error}
                </Markdown>
              </div>
            )}
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
