import type React from "react";
import { forwardRef } from "react";
import GooglecalendarIconSVG from "./googlecalendar";

export const GooglecalendarIcon = forwardRef<
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
      <GooglecalendarIconSVG ref={ref} {...props} />
    </span>
  );
});
