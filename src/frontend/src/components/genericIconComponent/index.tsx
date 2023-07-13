import { FC } from "react";
import SvgGoogle from "../../icons/Google/Google";
import SvgBing from "../../icons/Bing/Bing";
import { IconComponentProps, SvgIconProps } from "../../types/components";
import { svgIcons } from "../../utils";

export function IconFromSvg({ name }: SvgIconProps): JSX.Element {
  const TargetSvg = svgIcons[name]
  return (
    <TargetSvg />
  );
}

export default function IconComponent({ method, name }: IconComponentProps): JSX.Element {
  switch (method) {
    case 'SVG':
      return <IconFromSvg name={ name } />
  }
}