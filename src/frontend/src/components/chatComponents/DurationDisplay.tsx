import prettyMilliseconds from "pretty-ms";
import { useEffect, useState } from "react";
import Loading from "../ui/loading";
export default function DurationDisplay({ duration }: { duration?: number }) {
  const [elapsedTime, setElapsedTime] = useState(0);
  const [intervalId, setIntervalId] = useState<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // If duration is provided, clear any existing timer
    if (duration !== undefined && intervalId) {
      clearInterval(intervalId);
      setIntervalId(null);
      return;
    }

    // Start timer if duration is undefined
    if (duration === undefined && !intervalId) {
      const id = setInterval(() => {
        setElapsedTime((prev) => prev + 10); // Update every 10ms
      }, 10);
      setIntervalId(id);
    }

    // Cleanup
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [duration]);

  const displayTime = duration ?? elapsedTime;
  const humanizedTime = prettyMilliseconds(displayTime);
  return (
    <div
      className={`inline-flex items-center gap-2 rounded px-2 text-sm ${
        duration !== undefined
          ? "bg-emerald-950/30 text-emerald-400"
          : "text-gray-400"
      }`}
    >
      {humanizedTime}
      {duration === undefined && <Loading />}
    </div>
  );
}
