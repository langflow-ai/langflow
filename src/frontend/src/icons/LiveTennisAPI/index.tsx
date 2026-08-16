import type React from "react";
import { forwardRef } from "react";
import LiveTennisAPISVG from "./LiveTennisAPIIcon";

export const LiveTennisAPIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <LiveTennisAPISVG ref={ref} {...props} />;
});

export default LiveTennisAPIIcon;
