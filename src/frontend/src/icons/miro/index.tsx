import React, { forwardRef } from "react";
import SvgMiro from "./miro";

export const MiroIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    return (
      <span
        style={{
          display: "inline-grid",
          width: 20,
          height: 20,
          placeItems: "center",
          flexShrink: 0,
        }}
      >
        <SvgMiro ref={ref} {...props} />
      </span>
    );
  },
);
