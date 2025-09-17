import React, { forwardRef } from "react";
import DiscordIconSVG from "./discord";

export const DiscordIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <DiscordIconSVG ref={ref} {...props} />;
});
