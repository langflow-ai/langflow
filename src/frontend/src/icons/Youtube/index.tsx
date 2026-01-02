import React, { forwardRef } from "react";
import YoutubeIconSVG from "./youtube";

export const YoutubeIcon = forwardRef<
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
      <YoutubeIconSVG ref={ref} {...props} />
    </span>
  );
});
