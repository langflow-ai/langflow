import { useEffect, useState } from "react";
import { AnimatedNumber } from "../animatedNumbers";
import ForwardedIconComponent from "../genericIconComponent";
import Loading from "../ui/loading";

export default function DurationDisplay({ duration }: { duration?: number }) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [intervalId, setIntervalId] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (duration !== undefined && intervalId) {
      clearInterval(intervalId);
      setIntervalId(null);
      return;
    }

    if (duration === undefined && !intervalId) {
      const id = setInterval(() => {
        setElapsedTime((prev) => prev + 10);
      }, 10);
      setIntervalId(id);
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [duration]);

  const displayTime = duration ?? elapsedTime;
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
          className="tabular-nums"
        />
      </div>
    </div>
  );
}
