import { forwardRef, type SVGProps } from "react";
import TestMuAI from "./TestMuAI";

type TestMuAIIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The mark sits on its own dark tile, so one drawing reads on both light and
// dark backgrounds and isDark is accepted but not needed.
export const TestMuAIIcon = forwardRef<SVGSVGElement, TestMuAIIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <TestMuAI ref={ref} {...props} />,
);
