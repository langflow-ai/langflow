import { useEffect, useRef, useState } from "react";

interface UseMessageDurationProps {
  chatId: string;
  lastMessage: boolean;
  isBuilding: boolean;
  savedDuration?: number; // Duration from chat.properties.duration (for reload)
  onDurationFreeze?: (duration: number) => void; // Callback when duration freezes
}

interface UseMessageDurationResult {
  displayTime: number;
}

/**
 * Hook to track message duration (thinking time) for a single message.
 * Starts when message becomes active (lastMessage && isBuilding),
 * freezes when message becomes inactive or building stops.
 * Calls onDurationFreeze callback when duration is frozen.
 */
export function useMessageDuration({
  chatId,
  lastMessage,
  isBuilding,
  savedDuration,
  onDurationFreeze,
}: UseMessageDurationProps): UseMessageDurationResult {
  const [elapsedTime, setElapsedTime] = useState(savedDuration || 0);
  const frozenDurationRef = useRef<number | null>(savedDuration || null);
  const messageStartTimeRef = useRef<number | null>(null);
  const chatIdRef = useRef(chatId);
  const hasCalledFreezeCallback = useRef(false);

  // Consolidated effect: handle reset, start, stop, and freeze logic
  useEffect(() => {
    // Reset when chat.id changes
    if (chatIdRef.current !== chatId) {
      frozenDurationRef.current = savedDuration || null;
      messageStartTimeRef.current = null;
      setElapsedTime(savedDuration || 0);
      chatIdRef.current = chatId;
      hasCalledFreezeCallback.current = false;
    }

    const isActive = lastMessage && isBuilding;
    const hasStartTime = messageStartTimeRef.current !== null;
    const isFrozen = frozenDurationRef.current !== null;

    // Start timer when message becomes active
    if (isActive && !hasStartTime && !isFrozen) {
      messageStartTimeRef.current = Date.now();
      setElapsedTime(0);
    }

    // Freeze when message becomes inactive (no longer last message) or building stops
    if (hasStartTime && !isFrozen) {
      if (!isActive) {
        // Message is no longer active (either not last message or not building)
        const finalDuration = Date.now() - messageStartTimeRef.current!;
        if (finalDuration > 0) {
          frozenDurationRef.current = finalDuration;
          setElapsedTime(finalDuration);
          // Call freeze callback once
          if (onDurationFreeze && !hasCalledFreezeCallback.current) {
            hasCalledFreezeCallback.current = true;
            onDurationFreeze(finalDuration);
          }
        }
      } else if (!isBuilding && lastMessage) {
        // Building stopped but this is still the last message
        const finalDuration = Date.now() - messageStartTimeRef.current!;
        if (finalDuration > 0) {
          frozenDurationRef.current = finalDuration;
          setElapsedTime(finalDuration);
          // Call freeze callback once
          if (onDurationFreeze && !hasCalledFreezeCallback.current) {
            hasCalledFreezeCallback.current = true;
            onDurationFreeze(finalDuration);
          }
        }
      }
    }
  }, [chatId, lastMessage, isBuilding, savedDuration, onDurationFreeze]);

  // Live timer: only update when actively building
  useEffect(() => {
    const isActive = lastMessage && isBuilding;

    // Immediately stop timer if not active or already frozen
    if (
      !isActive ||
      !messageStartTimeRef.current ||
      frozenDurationRef.current !== null
    ) {
      // If we have a start time but are no longer active, freeze immediately
      if (
        messageStartTimeRef.current &&
        !isActive &&
        frozenDurationRef.current === null
      ) {
        const finalDuration = Date.now() - messageStartTimeRef.current;
        if (finalDuration > 0) {
          frozenDurationRef.current = finalDuration;
          setElapsedTime(finalDuration);
        }
      }
      return;
    }

    const interval = setInterval(() => {
      // Double-check we're still active before updating
      if (
        lastMessage &&
        isBuilding &&
        messageStartTimeRef.current &&
        frozenDurationRef.current === null
      ) {
        setElapsedTime(Date.now() - messageStartTimeRef.current);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [lastMessage, isBuilding]);

  const displayTime =
    frozenDurationRef.current !== null
      ? frozenDurationRef.current
      : elapsedTime;

  return { displayTime };
}
