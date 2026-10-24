import { forwardRef, useId } from "react";
import type { SVGProps } from "react";
import { useDarkStore } from "@/stores/darkStore";

export const FastAFIcon = forwardRef<SVGSVGElement, SVGProps<SVGSVGElement>>(
  (props, ref) => {
    const dark = useDarkStore((state) => state.dark);
    const gradientId = useId();
    return (
      <svg
        ref={ref}
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 32 32"
        width={24}
        height={24}
        {...props}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#8FE3E0" />
            <stop offset=".5" stopColor="#0ABAB5" />
            <stop offset="1" stopColor="#9AA2F0" />
          </linearGradient>
        </defs>
        <circle
          cx="16"
          cy="16"
          r="12.5"
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth="5"
        />
        <path
          fill={dark ? "#F4F4F5" : "#0E1116"}
          d="M17.4 8.6 11.4 17h4.1l-1 6.6 6.2-8.6h-4.2z"
        />
      </svg>
    );
  },
);

export default FastAFIcon;
