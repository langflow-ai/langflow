import type React from "react";
import { forwardRef } from "react";
import SvgSpecStream from "./SpecStreamIcon";

export const SpecStreamIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgSpecStream ref={ref} {...props} />;
});
