import React, { forwardRef } from "react";
import GoogledocsIconSVG from "./googledocs";

export const GoogledocsIcon = forwardRef<
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
      <GoogledocsIconSVG ref={ref} {...props} />
    </span>
  );
});
