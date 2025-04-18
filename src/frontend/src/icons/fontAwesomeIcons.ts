import * as fa from "react-icons/fa";
import * as faV6 from "react-icons/fa6";

export const fontAwesomeIcons = {
  ...fa,
  ...faV6,
};

export const isFontAwesomeIcon = (name: string): boolean => {
  return name.startsWith("Fa") && fontAwesomeIcons[name] !== undefined;
};
