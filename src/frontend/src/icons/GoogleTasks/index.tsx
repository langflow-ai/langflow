import React, { forwardRef } from "react";
import GoogleTasksIconSVG from "./googletasks";

export const GoogleTasksIcon = forwardRef<
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
      <GoogleTasksIconSVG ref={ref} {...props} />
    </span>
  );
});
