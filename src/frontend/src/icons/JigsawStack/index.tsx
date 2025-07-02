import React, { forwardRef } from "react";
import JigsawStackIconSVG from "./JigsawStackIcon";

export const JigsawStackIcon = forwardRef<
	SVGSVGElement,
	React.PropsWithChildren<{}>
>((props, ref) => {
	return <JigsawStackIconSVG ref={ref} {...props} />;
});
