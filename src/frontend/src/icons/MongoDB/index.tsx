import React, { forwardRef } from "react";
import SvgMongodbIcon from "./MongodbIcon";

export const MongoDBIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <SvgMongodbIcon ref={ref} {...props} />;
});
