import type React from "react";
import { forwardRef } from "react";
import GmailIconSVG from "./gmail";

export const GmailIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return (
      <span
        style={{
          display: "inline-grid",
          width: 22,
          height: 22,
          placeItems: "center",
          flexShrink: 0,
        }}
      >
        <GmailIconSVG ref={ref} {...props} />
      </span>
    );
  },
);
