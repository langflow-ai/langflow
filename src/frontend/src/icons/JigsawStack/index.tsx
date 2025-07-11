import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import JigsawStackIconSVG from "./JigsawStackIcon";

export const JigsawStackIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  const isdark = useDarkStore((state) => state.dark).toString();
  return <JigsawStackIconSVG ref={ref} {...props} isdark={isdark} />;
});
