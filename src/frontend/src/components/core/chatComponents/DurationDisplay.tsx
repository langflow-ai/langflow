import { useDurationStore } from "@/stores/durationStore";
import { useEffect, useRef } from "react";
import { AnimatedNumber } from "../../common/animatedNumbers";
import ForwardedIconComponent from "../../common/genericIconComponent";
import Loading from "../../ui/loading";

interface DurationDisplayProps {
  duration?: number;
  chatId: string;
  forceLoading?: boolean;
}

export default function DurationDisplay({
  duration,
  chatId,
  forceLoading = false,
}: DurationDisplayProps) {
  const {
    durations,
    setDuration,
    incrementDuration,
    clearInterval: clearDurationInterval,
    setInterval: setDurationInterval,
  } = useDurationStore();
  
  // Track if we're currently streaming/timing
  const isRunningRef = useRef(false);

  // Log the current props for debugging
  console.log("DurationDisplay props:", { duration, chatId, forceLoading, isRunning: isRunningRef.current });

  useEffect(() => {
    // Special case: -1 means "streaming started, maintain current timer"
    if (duration === -1) {
      // Don't update the duration, just ensure the timer is running
      const intervalId = setInterval(() => {
        incrementDuration(chatId);
      }, 10);
      
      isRunningRef.current = true;
      setDurationInterval(chatId, intervalId);
      return () => {
        clearDurationInterval(chatId);
      };
    }
    
    // Normal case: duration is defined (not undefined, not -1)
    if (duration !== undefined && duration !== -1) {
      setDuration(chatId, duration);
      clearDurationInterval(chatId);
      isRunningRef.current = false;
      return;
    }

    // Case: duration is undefined (start fresh timer)
    const intervalId = setInterval(() => {
      incrementDuration(chatId);
    }, 10);

    isRunningRef.current = true;
    setDurationInterval(chatId, intervalId);

    return () => {
      clearDurationInterval(chatId);
      isRunningRef.current = false;
    };
  }, [duration, chatId]);

  const displayTime = duration !== undefined && duration !== -1 ? duration : durations[chatId] ?? 0;
  const secondsValue = displayTime / 1000;
  const humanizedTime = `${secondsValue.toFixed(1)}s`;

  // determine if we should show loading state - either explicitly forced or running
  const showLoading = forceLoading || duration === undefined || duration === -1 || isRunningRef.current;
  
  return (
    <div
      data-testid="duration-display"
      className={`inline-flex items-center justify-between gap-1 rounded-[3px] px-2 text-sm ${
        !showLoading
          ? "bg-accent-emerald text-accent-emerald-foreground"
          : "bg-muted text-muted-foreground"
      }`}
    >
      {showLoading ? (
        <Loading className="h-4 w-4" />
      ) : (
        <ForwardedIconComponent name="check" className="h-4 w-4" />
      )}
      <div className="w-fit">
        <AnimatedNumber
          value={secondsValue}
          humanizedValue={humanizedTime}
          springOptions={{
            bounce: 0,
            duration: 300,
          }}
          className="text-xxs font-bold tabular-nums"
        />
      </div>
    </div>
  );
}
