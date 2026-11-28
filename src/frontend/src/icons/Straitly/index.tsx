import { forwardRef, type SVGProps } from "react";
import SvgStraitly from "./StraitlyIcon";

type StraitlyIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const StraitlyIcon = forwardRef<SVGSVGElement, StraitlyIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <SvgStraitly ref={ref} {...props} />,
);
