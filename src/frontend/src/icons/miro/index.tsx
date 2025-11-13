import React, { forwardRef } from "react";
import MiroIconSVG from "./miro";

export const MiroIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
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
        <MiroIconSVG ref={ref} {...props} />
      </span>
    );
  },
);
