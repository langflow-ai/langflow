import { forwardRef, type SVGProps } from "react";
import Keenable from "./Keenable";

type KeenableIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The colour mark paints its own eye whites and pupils, so one drawing reads on
// both light and dark backgrounds and isDark is accepted but not needed.
export const KeenableIcon = forwardRef<SVGSVGElement, KeenableIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Keenable ref={ref} {...props} />,
);
