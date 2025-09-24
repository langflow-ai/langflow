import React, { forwardRef } from "react";
import SvgMem from "./SvgMem";

export const Mem0IconComposio = forwardRef<
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
      <SvgMem className="icon" ref={ref} {...props} />
    </span>
  );
});
