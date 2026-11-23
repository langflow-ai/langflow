import { forwardRef, type SVGProps } from "react";
import Mnemoverse from "./Mnemoverse";

type MnemoverseIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The mark is a single cyan stroke that reads on both light and dark
// backgrounds, so isDark is accepted but not needed.
export const MnemoverseIcon = forwardRef<SVGSVGElement, MnemoverseIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Mnemoverse ref={ref} {...props} />,
);
