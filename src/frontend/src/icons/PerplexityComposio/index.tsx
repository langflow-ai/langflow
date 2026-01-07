import type React from "react";
import { forwardRef } from "react";
import PerplexitySVG from "./Perplexity";

export const PerplexityIconComposio = forwardRef<
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
      <PerplexitySVG ref={ref} {...props} />
    </span>
  );
});
