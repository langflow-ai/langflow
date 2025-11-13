import React, { forwardRef } from "react";
import MissiveIconSVG from "./missive";

export const MissiveIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
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
      <MissiveIconSVG ref={ref} {...props} />
    </span>
  );
});
