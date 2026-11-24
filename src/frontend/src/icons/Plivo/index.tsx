import { forwardRef, type SVGProps } from "react";
import Plivo from "./Plivo";

type PlivoIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const PlivoIcon = forwardRef<SVGSVGElement, PlivoIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Plivo ref={ref} {...props} />,
);
