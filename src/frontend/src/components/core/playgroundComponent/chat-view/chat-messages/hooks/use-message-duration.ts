import { useEffect, useRef, useState } from "react";

interface UseMessageDurationProps {
  lastMessage: boolean;
  isBuilding: boolean;
  buildStartTime: number | null;
  buildDuration: number | null;
}

interface UseMessageDurationResult {
  displayTime: number;
}

/**
 * Tracks flow execution time for the last bot message only.
 *
 * Guards on `lastMessage` prevent older messages from reacting to
 * global build state, so each message keeps its own frozen duration.
 */
export function useMessageDuration({
  lastMessage,
  isBuilding,
  buildStartTime,
  buildDuration,
}: UseMessageDurationProps): UseMessageDurationResult {
  const [elapsedTime, setElapsedTime] = useState(0);
  const frozenRef = useRef<number | null>(null);
  const buildStartRef = useRef<number | null>(null);

  useEffect(() => {
    if (!lastMessage || !buildStartTime) return;
    if (buildStartTime === buildStartRef.current) return;

    buildStartRef.current = buildStartTime;
    frozenRef.current = null;
    setElapsedTime(Date.now() - buildStartTime);
  }, [buildStartTime, lastMessage]);

  // Snap to exact backend duration once available
  useEffect(() => {
    if (!lastMessage || isBuilding) return;
    if (!buildStartRef.current || frozenRef.current !== null) return;
    if (buildDuration == null) return;

    frozenRef.current = buildDuration;
    setElapsedTime(buildDuration);
  }, [isBuilding, buildDuration, lastMessage]);

  useEffect(() => {
    if (
      !lastMessage ||
      !isBuilding ||
      !buildStartRef.current ||
      frozenRef.current !== null
    ) {
      return;
    }

    const tick = () => {
      if (!buildStartRef.current || frozenRef.current !== null) return;
      setElapsedTime(Date.now() - buildStartRef.current);
    };

    tick();
    const interval = setInterval(tick, 100);
    return () => clearInterval(interval);
  }, [lastMessage, isBuilding, buildStartTime]);

  const displayTime =
    frozenRef.current !== null ? frozenRef.current : elapsedTime;

  return { displayTime };
}
