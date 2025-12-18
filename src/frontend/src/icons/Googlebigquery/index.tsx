import React, { forwardRef } from "react";
import GooglebigqueryIconSVG from "./googlebigquery";

export const GooglebigqueryIcon = forwardRef<
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
      <GooglebigqueryIconSVG ref={ref} {...props} />
    </span>
  );
});
