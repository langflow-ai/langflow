import React, { forwardRef } from "react";
import SvgAmdocsLogo from "./Amdocs";

export const AmdocsIcon = forwardRef<
	SVGSVGElement,
	React.PropsWithChildren<{}>
>((props, ref) => {
	return <SvgAmdocsLogo ref={ref} {...props} />;
});
