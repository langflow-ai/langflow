import React, { forwardRef } from "react";
import LinearIconSVG from "./linear";

export const LinearIcon = forwardRef<
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
      <LinearIconSVG ref={ref} {...props} />
    </span>
  );
});
