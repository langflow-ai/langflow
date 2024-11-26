import { useDurationStore } from "@/stores/durationStore";
import { useEffect } from "react";
import { AnimatedNumber } from "../../common/animatedNumbers";
import ForwardedIconComponent from "../../common/genericIconComponent";
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
    incrementDuration,
    clearInterval: clearDurationInterval,
    setInterval: setDurationInterval,
  } = useDurationStore();

  useEffect(() => {
    if (duration !== undefined) {
      setDuration(chatId, duration);
      clearDurationInterval(chatId);
      return;
    }

    const intervalId = setInterval(() => {
      incrementDuration(chatId);
    }, 10);

    setDurationInterval(chatId, intervalId);

    return () => {
      clearDurationInterval(chatId);
    };
  }, [duration, chatId]);

  const displayTime = duration ?? durations[chatId] ?? 0;
  const secondsValue = displayTime / 1000;
  const humanizedTime = `${secondsValue.toFixed(1)}s`;

  return (
    <div
      className={`inline-flex items-center justify-between gap-1 rounded-[3px] px-2 text-sm ${
        duration !== undefined
          ? "bg-emerald-50 text-emerald-600 dark:bg-[#022C22] dark:text-emerald-500"
          : "bg-muted text-muted-foreground"
      }`}
    >
      {duration === undefined ? (
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
          className="text-[11px] font-bold tabular-nums"
        />
      </div>
    </div>
  );
}
