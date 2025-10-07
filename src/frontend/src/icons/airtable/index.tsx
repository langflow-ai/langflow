import React, { forwardRef } from "react";
import AirtableIconSVG from "./airtable";

export const AirtableIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{}>
>((props, ref) => {
  return <AirtableIconSVG ref={ref} {...props} />;
});
