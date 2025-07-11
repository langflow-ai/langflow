import { useDarkStore } from "@/stores/darkStore";
import type React from "react";
import { forwardRef } from "react";
import TwitterXSVG from "./TwitterX.jsx";

export const TwitterXIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <TwitterXSVG ref={ref} isdark={isdark} {...props} />;
});
