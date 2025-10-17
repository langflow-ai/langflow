import React, { forwardRef } from "react";
import BitbucketIconSVG from "./bitbucket";

export const BitbucketIcon = forwardRef<
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
      <BitbucketIconSVG ref={ref} {...props} />
    </span>
  );
});
