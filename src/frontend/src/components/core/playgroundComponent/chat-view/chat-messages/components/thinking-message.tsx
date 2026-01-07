import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useThinkingDurationStore } from "../hooks/use-thinking-duration";

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

  const formatTime = (ms: number) => {
    const seconds = ms / 1000;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  };

  const displayTime = isThinking ? elapsedTime : duration || 0;

  return (
    <div className="w-full py-2 word-break-break-word">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <ForwardedIconComponent
          name="Brain"
          className={`h-4 w-4 ${isThinking ? "text-primary animate-pulse" : "text-muted-foreground"}`}
        />
        <p className="m-0">
          {isThinking ? "Thinking for " : "Thought for "}
          {formatTime(displayTime)}
        </p>
      </div>
    </div>
  );
}
