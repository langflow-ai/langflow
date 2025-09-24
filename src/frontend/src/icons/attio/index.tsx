import React, { forwardRef } from "react";
import AttioIconSVG from "./attio";

export const AttioIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
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
        <AttioIconSVG ref={ref} {...props} />
      </span>
    );
  },
);
