import { forwardRef, type SVGProps } from "react";
import Keenable from "./Keenable";

type KeenableIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const KeenableIcon = forwardRef<SVGSVGElement, KeenableIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Keenable ref={ref} {...props} />,
);
