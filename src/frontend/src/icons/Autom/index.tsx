import { forwardRef, type SVGProps } from "react";
import Autom from "./Autom";

type AutomIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The brand mark keeps its colours on light and dark backgrounds, so isDark is
// accepted but not needed.
export const AutomIcon = forwardRef<SVGSVGElement, AutomIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Autom ref={ref} {...props} />,
);
