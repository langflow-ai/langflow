import type React from "react";
import { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import LiveTennisAPISVG from "./LiveTennisAPIIcon";

export const LiveTennisAPIIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isDark = useDarkStore((state) => state.dark);
  return <LiveTennisAPISVG ref={ref} isDark={isDark} {...props} />;
});

export default LiveTennisAPIIcon;
