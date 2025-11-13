import React, { forwardRef } from "react";
import DiscordIconSVG from "./discord";

export const DiscordIcon = forwardRef<
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
      <DiscordIconSVG ref={ref} {...props} />
    </span>
  );
});
