import type React from "react";
import { forwardRef } from "react";
import SvgSupabaseIcon from "./SupabaseIcon";

export const SupabaseIcon = forwardRef<
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
      <SvgSupabaseIcon ref={ref} {...props} />
    </span>
  );
});
