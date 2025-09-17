import { useEffect, useState } from "react";

export interface DurationDisplayProps {
  duration?: number;
  chatId: string;
}

export function DurationDisplay({ duration, chatId }: DurationDisplayProps) {
  const [currentDuration, setCurrentDuration] = useState(duration ?? 0);

  useEffect(() => {
    if (duration !== undefined) {
      setCurrentDuration(duration);
      return;
    }

    const intervalId = setInterval(() => {
      setCurrentDuration((prev) => prev + 10);
    }, 10);

    return () => {
      clearInterval(intervalId);
    };
  }, [duration, chatId]);

  const displayTime = duration ?? currentDuration;
  const secondsValue = displayTime / 1000;
  const humanizedTime =
    secondsValue < 0.05 ? "< 0.1s" : `${secondsValue.toFixed(1)}s`;

  return (
    <div
      data-testid="duration-display"
      className={`inline-flex items-center justify-between gap-1.5 rounded-[3px] px-2 text-sm ${
        duration !== undefined
          ? "text-accent-emerald-foreground"
          : "text-muted-foreground"
      }`}
    >
      {duration === undefined && (
        <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      <div className="w-fit">
        <span className="font-mono text-xs font-bold tabular-nums">
          {humanizedTime}
        </span>
      </div>
    </div>
  );
}
