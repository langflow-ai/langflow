import React, { forwardRef } from "react";
import ApolloIconSVG from "./apollo";

export const ApolloIcon = forwardRef<
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
      <ApolloIconSVG ref={ref} {...props} />
    </span>
  );
});
