import type React from "react";
import { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import NvidiaSVG from "./nvidia";

export const NvidiaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <NvidiaSVG ref={ref} isdark={isdark} {...props} />;
});
