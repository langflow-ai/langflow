import { forwardRef, type SVGProps } from "react";
import Sequenzy from "./Sequenzy";

type SequenzyIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The coral mark reads on both light and dark backgrounds, so one drawing is
// used for both themes and isDark is accepted but not needed.
export const SequenzyIcon = forwardRef<SVGSVGElement, SequenzyIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Sequenzy ref={ref} {...props} />,
);
