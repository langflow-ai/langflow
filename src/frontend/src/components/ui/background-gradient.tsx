import { cn } from "@/utils/utils";
import { motion } from "framer-motion";

import React from "react";

export const BackgroundGradient = ({
  children,
  className,
  containerClassName,
  animate = true,
}: {
  children?: React.ReactNode;
  className?: string;
  containerClassName?: string;
  animate?: boolean;
}) => {
  const variants = {
    initial: {
      backgroundPosition: "0 50%",
    },
    animate: {
      backgroundPosition: ["0, 50%", "100% 50%", "0 50%"],
    },
  };
  return (
    <div
      className={cn(
        "group relative rounded-3xl bg-[#141316] p-[2px]",
        containerClassName,
      )}
    >
      <motion.div
        variants={animate ? variants : undefined}
        initial={animate ? "initial" : undefined}
        animate={animate ? "animate" : undefined}
        transition={
          animate
            ? {
                duration: 5,
                repeat: Infinity,
                repeatType: "reverse",
              }
            : undefined
        }
        style={{
          backgroundSize: animate ? "400% 400%" : undefined,
        }}
        className={cn(
          "absolute inset-0 z-[1] rounded-3xl opacity-20 transition duration-500 will-change-transform group-hover:opacity-100 group-hover:blur-lg",
          "bg-[linear-gradient(180deg,rgba(171,102,255,0.7)_0%,rgba(171,102,255,0.7)_45%,rgba(171,102,255,0.2)_50%,rgba(171,102,255,0.15)_100%)]",
        )}
      />
      <motion.div
        variants={animate ? variants : undefined}
        initial={animate ? "initial" : undefined}
        animate={animate ? "animate" : undefined}
        transition={
          animate
            ? {
                duration: 5,
                repeat: Infinity,
                repeatType: "reverse",
              }
            : undefined
        }
        style={{
          backgroundSize: animate ? "400% 400%" : undefined,
        }}
        className={cn(
          "absolute inset-0 z-[1] rounded-3xl will-change-transform",
          "bg-[linear-gradient(180deg,rgba(171,102,255,0.7)_0%,rgba(171,102,255,0.7)_45%,rgba(171,102,255,0.2)_50%,rgba(171,102,255,0.15)_100%)]",
        )}
      />
      <div className={cn("relative z-10 rounded-3xl bg-[#141316]", className)}>
        {children}
      </div>
    </div>
  );
};
