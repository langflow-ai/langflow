// A faint dockyard watermark — Lothal was an ancient harbor where ships were
// built, so the dashboard sits over a quiet drydock: a pier and crane on the
// left, vessels on the water, gentle swell beneath. Pure decoration: it
// inherits `currentColor` (the caller picks the tint) and never intercepts
// pointer events. Anchored to the bottom and clipped, so it reads as a
// horizon behind the content rather than a centered illustration.

import type { CSSProperties } from "react";

export function HarborWatermark({
  style,
  opacity = 0.07,
}: {
  style?: CSSProperties;
  /** Overall strength of the watermark. Dark grounds can take a touch more. */
  opacity?: number;
}) {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        pointerEvents: "none",
        opacity,
        color: "currentColor",
        ...style,
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 1200 360"
        preserveAspectRatio="xMidYMax slice"
        fill="none"
        style={{ display: "block" }}
      >
        {/* Swell — three stepped wave lines along the waterline. */}
        <g
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          fill="none"
        >
          <path
            d="M-20 268 Q 70 256 160 268 T 340 268 T 520 268 T 700 268 T 880 268 T 1060 268 T 1240 268"
            opacity={0.55}
          />
          <path
            d="M-20 296 Q 70 284 160 296 T 340 296 T 520 296 T 700 296 T 880 296 T 1060 296 T 1240 296"
            opacity={0.38}
          />
          <path
            d="M-20 324 Q 70 312 160 324 T 340 324 T 520 324 T 700 324 T 880 324 T 1060 324 T 1240 324"
            opacity={0.24}
          />
        </g>

        {/* Pier + gantry crane on the left. */}
        <g
          stroke="currentColor"
          strokeWidth={2.4}
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
          opacity={0.8}
        >
          {/* Deck and pilings sinking into the water. */}
          <path d="M30 214 L300 214" />
          <path d="M70 214 L70 300" opacity={0.7} />
          <path d="M140 214 L140 300" opacity={0.7} />
          <path d="M210 214 L210 300" opacity={0.7} />
          <path d="M280 214 L280 300" opacity={0.7} />
          {/* Crane: mast, jib, back-stay, hoist line + load. */}
          <path d="M185 214 L185 86" />
          <path d="M185 96 L330 134" />
          <path d="M185 110 L122 150" />
          <path d="M308 129 L308 178" strokeWidth={1.8} />
          <rect x="296" y="178" width="24" height="18" rx="2" />
        </g>

        {/* Vessels in the harbor — a paper-boat motif echoing the Lothal mark. */}
        <g
          stroke="currentColor"
          strokeWidth={2.4}
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        >
          {/* Larger boat, mid-right. */}
          <g opacity={0.85}>
            <path d="M735 252 L905 252 L876 286 L764 286 Z" />
            <path d="M820 252 L820 168" />
            <path d="M820 176 L884 246 L820 246 Z" />
          </g>
          {/* Smaller boat, far right, lower on the horizon. */}
          <g opacity={0.55}>
            <path d="M988 268 L1086 268 L1069 290 L1005 290 Z" />
            <path d="M1037 268 L1037 214" />
            <path d="M1037 220 L1078 264 L1037 264 Z" />
          </g>
        </g>
      </svg>
    </div>
  );
}
