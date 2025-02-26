import React, { forwardRef } from "react";
import SVGContactRoundKey from "./ContactRoundKey";

export const ContactRoundKey = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ color?: string }>
>((props, ref) => {
  return <SVGContactRoundKey ref={ref} {...props} />;
});
