import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useThinkingDurationStore } from "../hooks/use-thinking-duration";
import { formatTime } from "../utils/format";

const TIMER_UPDATE_INTERVAL_MS = 100;

interface ThinkingMessageProps {
  isThinking: boolean;
  duration: number | null;
}

export default function ThinkingMessage({
  isThinking,
  duration,
}: ThinkingMessageProps) {
  const { startTime } = useThinkingDurationStore();
  const [elapsedTime, setElapsedTime] = useState(0);

  // Live timer while building
  useEffect(() => {
    if (!isThinking || !startTime) {
      return;
    }

    setElapsedTime(Date.now() - startTime);

    const interval = setInterval(() => {
      const start = useThinkingDurationStore.getState().startTime;
      if (start) {
        setElapsedTime(Date.now() - start);
      }
    }, TIMER_UPDATE_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [isThinking, startTime]);

  const displayTime = isThinking ? elapsedTime : duration || 0;

  return (
    <div className="w-full py-2 word-break-break-word">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {!isThinking && (
          <ForwardedIconComponent
            name="Check"
            className="h-4 w-4 text-emerald-400"
          />
        )}
        <p className="m-0 w-full flex justify-between">
          <span>{isThinking ? "Running..." : "Finished in"}</span>
          <span>{formatTime(displayTime)}</span>
        </p>
      </div>
    </div>
  );
}
