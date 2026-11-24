import type React from "react";
import { forwardRef } from "react";
import SvgMicrosoft from "./Microsoft";

type MicrosoftIconProps = React.SVGProps<SVGSVGElement> & { isDark?: boolean };

export const MicrosoftIcon = forwardRef<SVGSVGElement, MicrosoftIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SvgMicrosoft ref={ref} {...props} />,
);
