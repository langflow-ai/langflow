import React, { forwardRef } from "react";
import SvgOracleLogo from "./Oracle";

export const OracleIcon = forwardRef<
	SVGSVGElement,
	React.PropsWithChildren<{}>
>((props, ref) => {
	return <SvgOracleLogo ref={ref} {...props} />;
});