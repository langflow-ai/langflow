import React, { forwardRef } from "react";
import FigmaIconSVG from "./figma";

export const FigmaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
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
        <FigmaIconSVG ref={ref} {...props} />
      </span>
    );
  },
);
