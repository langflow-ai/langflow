import React, { forwardRef } from "react";
import HeygenIconSVG from "./heygen";

export const HeygenIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
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
      <HeygenIconSVG ref={ref} {...props} />
    </span>
  );
});
