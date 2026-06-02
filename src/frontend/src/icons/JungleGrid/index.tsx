import type React from "react";
import { forwardRef } from "react";
import { useDarkStore } from "@/stores/darkStore";
import JungleGridIconSvg from "./JungleGridIcon";

export const JungleGridIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();

  return <JungleGridIconSvg ref={ref} isdark={isdark} {...props} />;
});

export default JungleGridIcon;
