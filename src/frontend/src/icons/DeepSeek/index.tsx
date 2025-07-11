import { useDarkStore } from "@/stores/darkStore";
import type React from "react";
import { forwardRef } from "react";
import DeepSeekSVG from "./DeepSeekIcon";

export const DeepSeekIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <DeepSeekSVG ref={ref} isdark={isdark} {...props} />;
});
