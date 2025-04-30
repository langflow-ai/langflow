import { cn } from "@/utils/utils";
import { motion } from "framer-motion";
import React from "react";

export const BackgroundGradient = ({
  children,
  className,
  containerClassName,
  animate = true,
  borderColor,
  borderRadius,
}: {
  children?: React.ReactNode;
  className?: string;
  containerClassName?: string;
  animate?: boolean;
  borderColor?: string;
  borderRadius?: string;
}) => {
  const variants = {
    initial: {
      backgroundPosition: "0 50%",
    },
    animate: {
      backgroundPosition: ["0, 50%", "100% 50%", "0 50%"],
    },
  };

  const defaultGradient =
    "radial-gradient(circle farthest-side at 0 100%,#00ccb1,transparent),radial-gradient(circle farthest-side at 100% 0,#7b61ff,transparent),radial-gradient(circle farthest-side at 100% 100%,#ffc414,transparent),radial-gradient(circle farthest-side at 0 0,#1ca0fb,#141316)";

  return (
    <div className={cn("group relative p-[1px]", containerClassName)}>
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
          background: borderColor || defaultGradient,
          position: "absolute",
          inset: 0,
          borderRadius: "24px",
          opacity: 0.2,
          filter: "blur(8px)",
          transition: "all 0.4s ease-in-out",
          willChange: "transform",
        }}
        className="group-hover:filter-[blur(15px)] group-hover:opacity-70 group-hover:brightness-125"
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
        style={
          {
            backgroundSize: animate ? "400% 400%" : undefined,
            background: borderColor || defaultGradient,
            position: "absolute",
            inset: 0,
            borderRadius: borderRadius || "24px",
            willChange: "transform",
            transition: "all 0.4s ease-in-out",
            "--border-color": borderColor,
            "--border-color-transparent": borderColor
              ? `${borderColor}20`
              : undefined,
          } as React.CSSProperties
        }
        className={cn(
          "group-hover:brightness-125",
          borderColor
            ? "group-hover:shadow-[0_0_15px_3px_var(--border-color),0_0_25px_5px_var(--border-color-transparent)]"
            : "group-hover:shadow-[0_0_15px_3px_rgba(0,204,177,0.3),0_0_25px_5px_rgba(123,97,255,0.2)]",
        )}
      />

      <div className={cn("relative z-10", className)}>{children}</div>
    </div>
  );
};
