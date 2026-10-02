import type React from "react";
import { forwardRef } from "react";
import SvgLinkup from "./LinkupIcon";

export const LinkupIcon = forwardRef<
  SVGSVGElement,
  React.SVGProps<SVGSVGElement> & { isDark?: boolean }
>((props, ref) => {
  return <SvgLinkup ref={ref} {...props} />;
});
