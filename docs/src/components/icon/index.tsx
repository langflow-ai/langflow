import React from "react";
import CustomIcon from "../CustomIcon";

/*
How to use this component:

import Icon from "@site/src/components/icon";

<Icon name="AlertCircle" size={24} color="red" />
*/

type IconProps = {
  name: string;
  [key: string]: any; // Allow any other props to be passed through
};

export default function Icon({ name, ...props }: IconProps) {
  return <CustomIcon name={name} {...props} />;
} 