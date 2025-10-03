import type React from "react";
import { forwardRef } from "react";
import OutlookIconSVG from "./outlook";

export const OutlookIcon = forwardRef<
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
      <OutlookIconSVG ref={ref} {...props} />
    </span>
  );
});
