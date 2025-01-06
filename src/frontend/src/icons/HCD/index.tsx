import { useDarkStore } from "@/stores/darkStore";
import React, { forwardRef } from "react";
import HCDSVG from "./HCD";

export const HCDIcon = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    const isdark = useDarkStore((state) => state.dark).toString();

    return <HCDSVG ref={ref} isdark={isdark} {...props} />;
  },
);
