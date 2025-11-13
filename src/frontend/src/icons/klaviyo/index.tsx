import React, { forwardRef } from "react";
import KlaviyoIconSVG from "./klaviyo";

export const KlaviyoIcon = forwardRef<
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
      <KlaviyoIconSVG ref={ref} {...props} />
    </span>
  );
});
