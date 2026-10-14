import { forwardRef, type SVGProps } from "react";
import Looot from "./Looot";

type LoootIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const LoootIcon = forwardRef<SVGSVGElement, LoootIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Looot ref={ref} {...props} />,
);
