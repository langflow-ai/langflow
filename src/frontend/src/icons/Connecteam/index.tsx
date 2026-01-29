import React, { forwardRef } from "react";
import ConnecteamIconSVG from "./connecteam";

export const ConnecteamIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <ConnecteamIconSVG ref={ref} {...props} />;
});
