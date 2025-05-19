import { BorderTrail } from "@/components/core/border-trail";
import { Button } from "@/components/ui/button";
import { BuildStatus } from "@/constants/enums";
import { normalizeTimeString } from "@/CustomNodes/GenericNode/components/NodeStatus/utils/format-run-time";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";

export default function FlowBuildingComponent() {
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const flowBuildStatus = useFlowStore((state) => state.flowBuildStatus);
  const [error, setError] = useState<string | undefined>(undefined);
  const [duration, setDuration] = useState(0);
  const prevIsBuilding = useRef(isBuilding);

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

  return (
    <AnimatePresence>
      {(isBuilding || statusError.length > 0) && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          transition={{
            duration: 0.2,
            ease: "easeOut",
          }}
          className={cn(
            "absolute bottom-2 left-1/2 z-50 flex w-[530px] -translate-x-1/2 items-center justify-between gap-8 rounded-lg border bg-background px-4 py-2 text-sm font-medium shadow-md transition-all ease-in",
            !isBuilding && statusError.length === 0 && "translate-y-[120%]",
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
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="flex w-full items-center justify-between"
          >
            {statusBuilding.length > 0 ? (
              <span>Building component {statusBuilding[0]?.id}</span>
            ) : (
              <span>
                Error building component {statusError[0]?.id}:
                <br />
                {error}
              </span>
            )}
            <div className="flex items-center gap-2">
              {humanizedTime}
              <Button size="sm">Stop</Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
