import React, { forwardRef } from "react";
import CanvaIconSVG from "./canva";

export const CanvaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
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
        <CanvaIconSVG ref={ref} {...props} />
      </span>
    );
  },
);
