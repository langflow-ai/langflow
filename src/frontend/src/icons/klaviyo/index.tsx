import React, { forwardRef } from "react";
import SvgKlaviyo from "./klaviyo";

export const KlaviyoIcon = forwardRef<
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
      <SvgKlaviyo ref={ref} {...props} />
    </span>
  );
});
