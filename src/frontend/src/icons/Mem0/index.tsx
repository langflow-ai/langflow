import { useDarkStore } from "@/stores/darkStore";
import type React from "react";
import { forwardRef } from "react";
import SvgMem from "./SvgMem";

export const Mem0 = forwardRef<SVGSVGElement, React.PropsWithChildren<{}>>(
  (props, ref) => {
    const isdark = useDarkStore((state) => state.dark).toString();
    return <SvgMem className="icon" ref={ref} {...props} isdark={isdark} />;
  },
);
