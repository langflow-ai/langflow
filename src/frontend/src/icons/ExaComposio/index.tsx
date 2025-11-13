import type React from "react";
import { forwardRef } from "react";
import SvgExa from "./Exa";

export const ExaIconComposio = forwardRef<
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
      <SvgExa ref={ref} {...props} />
    </span>
  );
});
