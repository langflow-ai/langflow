import { forwardRef, type SVGProps } from "react";
import FaxForAgents from "./FaxForAgents";

type FaxForAgentsIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

export const FaxForAgentsIcon = forwardRef<
  SVGSVGElement,
  FaxForAgentsIconProps
>(({ isDark: _isDark, ...props }, ref) => (
  <FaxForAgents ref={ref} {...props} />
));
