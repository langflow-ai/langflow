import { forwardRef, type SVGProps } from "react";
import Clawifi from "./Clawifi";

type ClawifiIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The mark sits on its own dark tile, so one drawing reads on both light and
// dark backgrounds and isDark is accepted but not needed.
export const ClawifiIcon = forwardRef<SVGSVGElement, ClawifiIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Clawifi ref={ref} {...props} />,
);
