import React, { forwardRef } from "react";
import GooglemeetIconSVG from "./googlemeet";

export const GooglemeetIcon = forwardRef<
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
      <GooglemeetIconSVG ref={ref} {...props} />
    </span>
  );
});
