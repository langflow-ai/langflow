import React, { forwardRef } from "react";
import ContentfulIconSVG from "./contentful";

export const ContentfulIcon = forwardRef<
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
      <ContentfulIconSVG ref={ref} {...props} />
    </span>
  );
});
