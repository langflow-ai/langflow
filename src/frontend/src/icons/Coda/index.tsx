import React, { forwardRef } from "react";
import CodaIconSVG from "./coda";

export const CodaIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
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
        <CodaIconSVG ref={ref} {...props} />
      </span>
    );
  },
);
