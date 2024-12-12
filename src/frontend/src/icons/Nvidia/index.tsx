import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import NvidiaSVG from "./nvidia";

export const NvidiaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <NvidiaSVG ref={ref} isdark={isdark} {...props} />;
});
