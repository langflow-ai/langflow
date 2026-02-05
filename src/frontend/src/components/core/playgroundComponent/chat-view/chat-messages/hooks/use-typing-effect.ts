import { useEffect, useRef, useState } from "react";

interface UseTypingEffectProps {
  text: string;
  willAnimate: boolean; // Should this message animate at all? (captured at mount)
  canStart: boolean; // Can typing start now? (e.g., build is done)
  speed?: number; // characters per interval
  interval?: number; // ms between updates
  onComplete?: () => void;
}

export function useTypingEffect({
  text,
  willAnimate,
  canStart,
  speed = 3,
  interval = 30,
  onComplete,
}: UseTypingEffectProps) {
  // Initialize: if willAnimate, start empty; otherwise show full text
  const [displayedText, setDisplayedText] = useState(() =>
    willAnimate ? "" : text,
  );
  const [isTyping, setIsTyping] = useState(false);
  const indexRef = useRef(0);
  const hasCompletedRef = useRef(false);

  useEffect(() => {
    // If not meant to animate, always show full text
    if (!willAnimate) {
      setDisplayedText(text);
      setIsTyping(false);
      return;
    }

    // If meant to animate but can't start yet, show empty (waiting)
    if (!canStart) {
      return;
    }

    // If already completed, show full text
    if (hasCompletedRef.current) {
      setDisplayedText(text);
      setIsTyping(false);
      return;
    }

    // If text is empty, nothing to type
    if (text.length === 0) {
      setIsTyping(false);
      return;
    }

    setIsTyping(true);

    const timer = setInterval(() => {
      if (indexRef.current < text.length) {
        const nextIndex = Math.min(indexRef.current + speed, text.length);
        setDisplayedText(text.slice(0, nextIndex));
        indexRef.current = nextIndex;
      } else {
        setIsTyping(false);
        hasCompletedRef.current = true;
        clearInterval(timer);
        onComplete?.();
      }
    }, interval);

    return () => clearInterval(timer);
  }, [text, willAnimate, canStart, speed, interval, onComplete]);

  return { displayedText, isTyping };
}
