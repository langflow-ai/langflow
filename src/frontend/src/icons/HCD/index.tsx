import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import HCDSVG from "./HCD";

export const HCDIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    const isDark = useDarkStore((state) => state.dark);

    return <HCDSVG ref={ref} isDark={isDark} {...props} />;
  },
);
