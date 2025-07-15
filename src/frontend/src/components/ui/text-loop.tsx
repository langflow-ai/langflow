"use client";

import {
  AnimatePresence,
  type AnimatePresenceProps,
  motion,
  type Transition,
  type Variants,
} from "framer-motion";
import { Children, useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/utils/utils";

export type TextLoopProps = {
  children: React.ReactNode | React.ReactNode[];
  className?: string;
  interval?: number;
  transition?: Transition;
  variants?: Variants;
  onIndexChange?: (index: number) => void;
  trigger?: boolean;
  mode?: AnimatePresenceProps["mode"];
  style?: React.CSSProperties;
};

export function TextLoop({
  children,
  className,
  interval = 2,
  transition = { duration: 0.3 },
  variants,
  onIndexChange,
  trigger = true,
  mode = "popLayout",
  style,
}: TextLoopProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const items = Children.toArray(children);
  const timerRef = useRef<NodeJS.Timeout>();

  const updateIndex = useCallback(() => {
    setCurrentIndex((current) => {
      const next = (current + 1) % items.length;
      onIndexChange?.(next);
      return next;
    });
  }, [items.length, onIndexChange]);

  useEffect(() => {
    if (!trigger || items.length <= 1) return;

    const intervalMs = interval * 1000;
    timerRef.current = setInterval(updateIndex, intervalMs);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [trigger, interval, items.length, updateIndex]);

  const motionVariants: Variants = {
    initial: { y: 20, opacity: 0 },
    animate: { y: 0, opacity: 1 },
    exit: { y: -20, opacity: 0 },
  };

  if (items.length === 1) {
    return (
      <div className={cn("relative inline-block whitespace-nowrap", className)}>
        <motion.div
          initial="initial"
          animate="animate"
          transition={transition}
          variants={variants || motionVariants}
          style={style}
        >
          {items[0]}
        </motion.div>
      </div>
    );
  }

  return (
    <div className={cn("relative inline-block whitespace-nowrap", className)}>
      <AnimatePresence mode={mode} initial={false}>
        <motion.div
          key={currentIndex}
          initial="initial"
          animate="animate"
          exit="exit"
          transition={transition}
          variants={variants || motionVariants}
          style={style}
        >
          {items[currentIndex]}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
