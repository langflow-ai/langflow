import { useEffect } from "react";
import { useDurationStore } from "@/stores/durationStore";
import { AnimatedNumber } from "../../common/animatedNumbers";
import Loading from "../../ui/loading";

interface DurationDisplayProps {
  duration?: number;
  chatId: string;
}

export default function DurationDisplay({
  duration,
  chatId,
}: DurationDisplayProps) {
  const {
    durations,
    setDuration,
    startTimer,
    clearInterval: clearDurationInterval,
    setInterval: setDurationInterval,
  } = useDurationStore();

  useEffect(() => {
    if (duration !== undefined) {
      setDuration(chatId, duration);
      clearDurationInterval(chatId);
      return;
    }

    // Start timer with current timestamp
    startTimer(chatId);

    const intervalId = setInterval(() => {
      // Update duration based on elapsed time from start
      const startTime = useDurationStore.getState().startTimes[chatId];
      if (startTime) {
        const elapsed = Date.now() - startTime;
        setDuration(chatId, elapsed);
      }
    }, 100);

    setDurationInterval(chatId, intervalId);

    return () => {
      clearDurationInterval(chatId);
    };
  }, [duration, chatId]);

  const displayTime = duration ?? durations[chatId] ?? 0;
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
      {duration === undefined && <Loading className="h-3 w-3" />}
      <div className="w-fit">
        <AnimatedNumber
          value={secondsValue}
          humanizedValue={humanizedTime}
          springOptions={{
            bounce: 0,
            duration: 300,
          }}
          className="font-mono text-xxs font-bold tabular-nums"
        />
      </div>
    </div>
  );
}
