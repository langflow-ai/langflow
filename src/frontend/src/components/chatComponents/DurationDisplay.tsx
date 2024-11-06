import { AnimatedNumber } from "@/components/animatedNumbers";
import prettyMilliseconds from "pretty-ms";
import { useEffect, useState } from "react";
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

  return (
    <div
      className={`inline-flex items-center gap-2 rounded px-2 text-sm ${
        duration !== undefined
          ? "bg-emerald-950/30 text-emerald-400"
          : "text-gray-400"
      }`}
    >
      <AnimatedNumber
        value={displayTime}
        springOptions={{
          bounce: 0,
          duration: 300,
        }}
        className="tabular-nums"
      />
      {duration === undefined && <Loading />}
    </div>
  );
}
