import type React from "react";
import { forwardRef } from "react";
import SvgGenMagic from "./GenMagic";

export const GenMagicIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgGenMagic ref={ref} {...props} />;
});
