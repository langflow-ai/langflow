import React, { forwardRef } from "react";
import SvgEricssonLogo from "./Ericsson";

export const EricssonIcon = forwardRef<
	SVGSVGElement,
	React.PropsWithChildren<{}>
>((props, ref) => {
	return <SvgEricssonLogo ref={ref} {...props} />;
});