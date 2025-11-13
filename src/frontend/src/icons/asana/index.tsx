import React, { forwardRef } from "react";
import AsanaIconSVG from "./asana";

export const AsanaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
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
        <AsanaIconSVG ref={ref} {...props} />
      </span>
    );
  },
);
