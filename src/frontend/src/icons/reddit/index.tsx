import React, { forwardRef } from "react";
import RedditIconSVG from "./reddit";

export const RedditIcon = forwardRef<
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
      <RedditIconSVG ref={ref} {...props} />
    </span>
  );
});
